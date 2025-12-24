"""Projection Fetcher Service - Fetch projections from Razzball API"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models import Player, ProjectionDaily
from app.config import get_settings
import pandas as pd

settings = get_settings()


class ProjectionFetcher:
    """Fetch and store player projections"""

    def __init__(self, db: Session):
        self.db = db
        self.api_key = settings.RAZZBALL_API_KEY
        self.base_url = settings.RAZZBALL_API_BASE_URL

    def fetch_daily_projections(self, date: str = None) -> Optional[List[Dict]]:
        """
        Fetch daily projections from Razzball API

        Args:
            date: Date string in YYYY-MM-DD format (default: yesterday)

        Returns:
            List of projection dicts or None if error
        """
        if not date:
            # Default to yesterday (most recent data)
            yesterday = datetime.now() - timedelta(days=1)
            date = yesterday.strftime("%Y-%m-%d")

        url = f"{self.base_url}/projections/daily/{date}"
        headers = {
            "Razzball-Api-Key": self.api_key,
            "Accept": "application/vnd.razzball-v1+json"
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️  API returned status {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ Error fetching projections: {str(e)}")
            return None

    def parse_daily_csv(self, csv_path: str) -> List[Dict]:
        """
        Parse daily projection CSV (backup if API fails)

        Args:
            csv_path: Path to Razzball daily CSV

        Returns:
            List of projection dicts
        """
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        projections = []

        for _, row in df.iterrows():
            projection = {
                'razzball_id': int(row['RazzID']),
                'name': row['Name'],
                'mlb_team': row['Team'],
                'position': row.get('ESPN') or row.get('Y!'),
                'pa': float(row['PA']) if pd.notna(row['PA']) else None,
                'ab': float(row['AB']) if pd.notna(row['AB']) else None,
                'h': float(row['H']) if pd.notna(row['H']) else None,
                'r': float(row['R']) if pd.notna(row['R']) else None,
                'hr': float(row['HR']) if pd.notna(row['HR']) else None,
                'rbi': float(row['RBI']) if pd.notna(row['RBI']) else None,
                'sb': float(row['SB']) if pd.notna(row['SB']) else None,
                'bb': float(row['BB']) if pd.notna(row['BB']) else None,
                'so': float(row['SO']) if pd.notna(row['SO']) else None,
                'avg': float(row['AVG']) if pd.notna(row['AVG']) else None,
                'obp': float(row['OBP']) if pd.notna(row['OBP']) else None,
                'slg': float(row['SLG']) if pd.notna(row['SLG']) else None,
            }
            projections.append(projection)

        return projections

    def store_daily_projections(self, projections: List[Dict], date: str = None) -> int:
        """
        Store daily projections in database

        Args:
            projections: List of projection dicts
            date: Date for projections

        Returns:
            Number of projections stored
        """
        if not date:
            yesterday = datetime.now() - timedelta(days=1)
            date = yesterday.strftime("%Y-%m-%d")

        projection_date = datetime.strptime(date, "%Y-%m-%d").date()
        stored_count = 0

        for proj_data in projections:
            # Find or create player
            player = self.db.query(Player).filter(
                Player.razzball_id == proj_data['razzball_id']
            ).first()

            if not player:
                # Create new player
                player = Player(
                    razzball_id=proj_data['razzball_id'],
                    name=proj_data['name'],
                    team=proj_data.get('mlb_team'),
                    position=proj_data.get('position')
                )
                self.db.add(player)
                self.db.flush()

            # Check if projection already exists
            existing = self.db.query(ProjectionDaily).filter(
                ProjectionDaily.player_id == player.id,
                ProjectionDaily.date == projection_date
            ).first()

            if existing:
                # Update existing
                for key, value in proj_data.items():
                    if key not in ['razzball_id', 'name', 'mlb_team', 'position'] and value is not None:
                        setattr(existing, key, value)
            else:
                # Create new projection
                projection = ProjectionDaily(
                    player_id=player.id,
                    date=projection_date,
                    pa=proj_data.get('pa'),
                    ab=proj_data.get('ab'),
                    h=proj_data.get('h'),
                    r=proj_data.get('r'),
                    hr=proj_data.get('hr'),
                    rbi=proj_data.get('rbi'),
                    sb=proj_data.get('sb'),
                    bb=proj_data.get('bb'),
                    so=proj_data.get('so'),
                    avg=proj_data.get('avg'),
                    obp=proj_data.get('obp'),
                    slg=proj_data.get('slg'),
                )
                self.db.add(projection)

            stored_count += 1

        self.db.commit()
        return stored_count

    def sync_daily_projections(self, date: str = None, fallback_csv: str = None) -> int:
        """
        Sync daily projections - try API first, fallback to CSV

        Args:
            date: Date string
            fallback_csv: Path to CSV file as backup

        Returns:
            Number of projections synced
        """
        # Try API first
        projections = self.fetch_daily_projections(date)

        # Fallback to CSV if API fails
        if not projections and fallback_csv:
            print("⚠️  API failed, using CSV fallback...")
            projections = self.parse_daily_csv(fallback_csv)

        if projections:
            count = self.store_daily_projections(projections, date)
            print(f"✅ Synced {count} daily projections")
            return count
        else:
            print("❌ No projections available")
            return 0


# Test the fetcher
if __name__ == "__main__":
    from app.database import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    fetcher = ProjectionFetcher(db)

    print("\n🧪 Testing Projection Fetcher\n")

    # Test with CSV (since we have the file)
    csv_path = "../../Csvs/Razzball_Daily_Hitters.csv"

    try:
        projections = fetcher.parse_daily_csv(csv_path)
        print(f"✅ Parsed {len(projections)} projections from CSV")
        print(f"\n📋 Sample projection:")
        print(projections[0])

        # Store them
        count = fetcher.store_daily_projections(projections)
        print(f"\n✅ Stored {count} projections in database")

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    db.close()
