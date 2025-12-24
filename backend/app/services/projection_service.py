"""Razzball API Projection Service - Fetch player projections from official Razzball APIs"""
import pandas as pd
import requests
import cloudscraper
from typing import Dict, List, Optional
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Global cache for projections (shared across all instances)
_PROJECTION_CACHE = {}


class ProjectionService:
    """Fetch player projections from Razzball APIs"""

    # Official Razzball API URLs
    API_BASE_URL = os.getenv("RAZZBALL_API_BASE_URL", "https://api.razzball.com/mlb")
    API_KEY = os.getenv("RAZZBALL_API_KEY")

    # Projection endpoints
    DAILY_URL = f"{API_BASE_URL}/projections/botdaily"
    WEEKLY_URL = f"{API_BASE_URL}/projections/botweekly"
    ROS_URL = f"{API_BASE_URL}/projections/botros"  # Rest of Season

    def __init__(self, projection_type: str = "ros"):
        """
        Initialize projection service

        Args:
            projection_type: Type of projections - 'daily', 'weekly', or 'ros' (default: 'ros')
        """
        self.projection_type = projection_type
        self.projections_cache = None

        # Select API URL based on projection type
        if projection_type == "daily":
            self.api_url = self.DAILY_URL
        elif projection_type == "weekly":
            self.api_url = self.WEEKLY_URL
        else:
            self.api_url = self.ROS_URL

    def fetch_projections(self) -> pd.DataFrame:
        """
        Fetch projections from Razzball API (with global caching)

        Returns:
            DataFrame with player projections
        """
        global _PROJECTION_CACHE

        # Check global cache first
        if self.projection_type in _PROJECTION_CACHE:
            logger.info(f"Using cached {self.projection_type} projections ({len(_PROJECTION_CACHE[self.projection_type])} players)")
            return _PROJECTION_CACHE[self.projection_type]

        try:
            # Set up headers based on Rudy's working Postman example
            headers = {
                'User-Agent': 'PostmanRuntime/7.49.1',
                'Accept': 'application/vnd.razzball-v1+json',
                'Connection': 'keep-alive'
            }
            # Note: Don't specify Accept-Encoding - requests handles it automatically

            if self.API_KEY:
                # Use the correct header name from Postman
                headers['Razzball-Api-Key'] = self.API_KEY

            # Use standard requests (Cloudflare now allows access)
            logger.info(f"Fetching {self.projection_type} projections from {self.api_url}")
            response = requests.get(self.api_url, headers=headers, timeout=120)  # 2 minutes for large response
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response size: {len(response.content)} bytes")
            response.raise_for_status()

            # Parse JSON response
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Failed to parse JSON. Response preview: {response.text[:500]}")
                raise

            # Convert to DataFrame
            # API should return a list of player objects
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict) and 'players' in data:
                df = pd.DataFrame(data['players'])
            elif isinstance(data, dict) and 'data' in data:
                df = pd.DataFrame(data['data'])
            else:
                df = pd.DataFrame(data)

            # Cache globally for fast subsequent requests
            _PROJECTION_CACHE[self.projection_type] = df
            logger.info(f"Fetched {len(df)} player projections from Razzball API (cached for future requests)")
            return df

        except Exception as e:
            logger.error(f"Error fetching projections from API: {str(e)}")
            # Return cached version if available
            if self.projection_type in _PROJECTION_CACHE:
                logger.warning("Using cached projections from previous fetch")
                return _PROJECTION_CACHE[self.projection_type]
            raise

    def get_player_projection(self, player_name: str) -> Optional[Dict]:
        """
        Get projection for a specific player by name

        Args:
            player_name: Player name to search for

        Returns:
            Dict with player projection data or None
        """
        try:
            df = self.fetch_projections()

            # API may use different column names - try multiple variations
            name_columns = ['Name', 'name', 'player_name', 'playerName', 'Player']
            name_col = None

            for col in name_columns:
                if col in df.columns:
                    name_col = col
                    break

            if name_col is None:
                logger.warning(f"No name column found in projections. Available columns: {list(df.columns)}")
                return None

            # Clean the search name
            search_name = player_name.lower().strip()

            # Clean API names (remove [player id=XXX] tags)
            import re
            df_clean = df.copy()
            df_clean['clean_name'] = df_clean[name_col].apply(
                lambda x: re.sub(r'\[player id=\d+\]|\[/player\]', '', str(x)).strip().lower()
            )

            # Try exact match first
            player_row = df_clean[df_clean['clean_name'] == search_name]

            if player_row.empty:
                # Try partial match - check if search name is in the clean name
                player_row = df_clean[df_clean['clean_name'].str.contains(search_name, na=False, regex=False)]

            if player_row.empty:
                # Try reverse - check if any word from clean name is in search name
                for idx, row in df_clean.iterrows():
                    clean = row['clean_name']
                    if clean and len(clean) > 3:  # Avoid matching very short names
                        # Split both names and check for common words
                        search_words = set(search_name.split())
                        clean_words = set(clean.split())
                        if len(search_words & clean_words) >= 2:  # At least 2 words match (first + last name)
                            player_row = df_clean.loc[[idx]]
                            break

            if not player_row.empty:
                # Return first match as dict (without clean_name column)
                result = player_row.iloc[0].to_dict()
                if 'clean_name' in result:
                    del result['clean_name']
                return result

            return None

        except Exception as e:
            logger.error(f"Error getting player projection: {str(e)}")
            return None

    def get_top_free_agents(
        self,
        position: Optional[str] = None,
        stat: str = 'HR',
        limit: int = 10
    ) -> List[Dict]:
        """
        Get top free agents by a specific stat

        Args:
            position: Filter by position (optional)
            stat: Stat to sort by (default: HR)
            limit: Number of players to return

        Returns:
            List of player projection dicts
        """
        try:
            df = self.fetch_projections()

            # Try to find position column
            pos_columns = ['Pos', 'pos', 'position', 'Position']
            pos_col = None

            for col in pos_columns:
                if col in df.columns:
                    pos_col = col
                    break

            # Filter by position if specified
            if position and pos_col:
                df = df[df[pos_col].str.contains(position, na=False, case=False)]

            # Try to find stat column (case insensitive)
            stat_col = None
            for col in df.columns:
                if col.upper() == stat.upper():
                    stat_col = col
                    break

            # Sort by stat (descending) and get top N
            if stat_col:
                top_players = df.nlargest(limit, stat_col)
                return top_players.to_dict('records')
            else:
                logger.warning(f"Stat '{stat}' not found in projections. Available columns: {list(df.columns)}")
                return []

        except Exception as e:
            logger.error(f"Error getting top free agents: {str(e)}")
            return []


# Test the service
if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing Razzball API Projection Service")
    print("="*60)

    # Test all three projection types
    for proj_type in ['ros', 'daily', 'weekly']:
        print(f"\n--- Testing {proj_type.upper()} projections ---")
        service = ProjectionService(projection_type=proj_type)

        try:
            print("Fetching projections from API...")
            df = service.fetch_projections()
            print(f"[OK] Fetched {len(df)} players")
            print(f"[OK] Columns: {list(df.columns)[:10]}...")  # Show first 10 columns

            # Test getting a player
            print("\nTesting player lookup:")
            player = service.get_player_projection("Aaron Judge")
            if player:
                # Find name column
                name_key = next((k for k in player.keys() if 'name' in k.lower()), 'Name')
                print(f"[OK] Found: {player.get(name_key, 'Unknown')}")

                # Try to find stat columns
                hr_key = next((k for k in player.keys() if k.upper() == 'HR'), None)
                rbi_key = next((k for k in player.keys() if k.upper() == 'RBI'), None)

                if hr_key and rbi_key:
                    print(f"    HR: {player.get(hr_key)}, RBI: {player.get(rbi_key)}")
            else:
                print("[WARN] Player not found")

        except Exception as e:
            print(f"[ERROR] Failed to fetch {proj_type} projections: {str(e)}")

    print("\n" + "="*60)
    print("Testing complete!")
    print("="*60)
