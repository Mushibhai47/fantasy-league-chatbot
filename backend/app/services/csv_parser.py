"""CSV Parser Service - Parse league CSVs from Fantrax, CBS Sports, NFBC"""
import pandas as pd
from typing import List, Dict, Optional
import re


class CSVParser:
    """Parse fantasy league CSV files"""

    @staticmethod
    def detect_league_type(df: pd.DataFrame) -> str:
        """
        Detect which league platform the CSV is from
        Returns: 'fantrax', 'cbs', 'nfbc', or 'unknown'
        """
        columns = [col.lower().strip() for col in df.columns]

        # Fantrax has unique 'ID' column with format like *05ajh*
        if 'id' in columns:
            # Find the actual column name (case-insensitive)
            id_col = [col for col in df.columns if col.lower().strip() == 'id'][0]
            if pd.notna(df[id_col].iloc[0]) and str(df[id_col].iloc[0]).startswith('*'):
                return 'fantrax'

        # CBS Sports has 'Avail' column (team owner name)
        if 'avail' in columns:
            return 'cbs'

        # NFBC has 'Owner' column and numeric 'id'
        if 'owner' in columns and 'id' in columns:
            return 'nfbc'

        return 'unknown'

    @staticmethod
    def parse_fantrax(file_path: str) -> List[Dict]:
        """
        Parse Fantrax CSV
        Format: ID,Player,Team,Position,RkOv,Status,Score,Ros
        Example: *05ajh*,Garrett Crochet,BOS,SP,1,AA,100,-

        Status field meanings:
        - "FA" = Free Agent
        - Team owner name (AA, MG, Doc, etc.) = Owned player
        - Empty/'-' = Free Agent
        """
        df = pd.read_csv(file_path)
        players = []

        for _, row in df.iterrows():
            # Check Status field for free agent designation
            status = row['Status']

            if pd.notna(status) and str(status).strip() not in ['-', '', 'FA']:
                # Has a team owner name (not FA, not empty)
                owner = str(status).strip()
            else:
                # Status is "FA", empty, or "-" = Free Agent
                owner = 'Free Agent'

            player = {
                'fantrax_id': row['ID'],  # *05ajh*
                'name': row['Player'],
                'mlb_team': row['Team'],  # BOS, NYY, etc.
                'position': row['Position'],  # SP, OF, etc.
                'owner': owner,
                'league_type': 'fantrax',
                'status': str(status) if pd.notna(status) else None  # Keep original status for reference
            }
            players.append(player)

        return players

    @staticmethod
    def parse_cbs(file_path: str) -> List[Dict]:
        """
        Parse CBS Sports CSV
        Format: Avail,Player,AB,R,H,1B,2B,3B,HR,RBI,BB,K,SB,CS,AVG,OBP,SLG,Rank
        Example: The Itch,"Shohei Ohtani P,U | LAD ",611,146,172,...

        Note: NO player IDs in CBS - will need fuzzy matching
        """
        # CBS files have a title row before the header, skip it
        df = pd.read_csv(file_path, skiprows=1)
        players = []

        for _, row in df.iterrows():
            # Avail column contains team owner name OR is empty for free agents
            avail_val = row['Avail']
            if pd.notna(avail_val) and isinstance(avail_val, str) and avail_val.strip() != '':
                owner = avail_val.strip()
            else:
                owner = 'Free Agent'

            # Player column format: "Name Position | Team"
            # Example: "Shohei Ohtani P,U | LAD "
            player_str = str(row['Player'])

            # Extract name and team
            if '|' in player_str:
                name_pos, mlb_team = player_str.split('|')
                mlb_team = mlb_team.strip()

                # Extract just the name (before position abbreviations)
                # Position is usually at the end: "Shohei Ohtani P,U"
                name = re.sub(r'\s+[A-Z,]+\s*$', '', name_pos).strip()
            else:
                name = player_str.strip()
                mlb_team = None

            player = {
                'fantrax_id': None,  # CBS has no IDs
                'nfbc_id': None,
                'name': name,
                'mlb_team': mlb_team,
                'position': None,  # Could extract from Player string if needed
                'owner': owner,
                'league_type': 'cbs'
            }
            players.append(player)

        return players

    @staticmethod
    def parse_nfbc(file_path: str) -> List[Dict]:
        """
        Parse NFBC CSV
        Format: id,Players,Owner,Injury,Pos,Team,Own %,Start %,...
        Example: 11802,"Abbott, Andrew",Matt Cathey - TARF,,P,CIN,100,82,...
        """
        df = pd.read_csv(file_path)
        players = []

        for _, row in df.iterrows():
            # Owner column contains team owner name OR is empty for free agents
            owner = row['Owner'] if pd.notna(row['Owner']) and row['Owner'].strip() != '' else 'Free Agent'

            player = {
                'nfbc_id': int(row['id']),
                'name': row['Players'],
                'mlb_team': row['Team'],
                'position': row['Pos'],
                'owner': owner,
                'league_type': 'nfbc'
            }
            players.append(player)

        return players

    @staticmethod
    def parse_csv(file_path: str) -> tuple[List[Dict], str]:
        """
        Auto-detect league type and parse CSV
        Returns: (players_list, league_type)
        """
        # Try reading normally first
        try:
            df_sample = pd.read_csv(file_path, nrows=5)
            league_type = CSVParser.detect_league_type(df_sample)
        except:
            league_type = 'unknown'

        # If detection failed, try skipping first row (CBS format)
        if league_type == 'unknown':
            try:
                df_sample = pd.read_csv(file_path, skiprows=1, nrows=5)
                league_type = CSVParser.detect_league_type(df_sample)
            except:
                pass

        if league_type == 'fantrax':
            players = CSVParser.parse_fantrax(file_path)
        elif league_type == 'cbs':
            players = CSVParser.parse_cbs(file_path)
        elif league_type == 'nfbc':
            players = CSVParser.parse_nfbc(file_path)
        else:
            raise ValueError(f"Unknown CSV format. Could not detect league type.")

        return players, league_type


# Test the parser
if __name__ == "__main__":
    import sys
    import os

    # Test files (update paths as needed)
    test_files = {
        'fantrax': '../../Csvs/Fantrax League Player File.csv',
        'cbs': '../../Csvs/CBSSports League Player File.csv',
        'nfbc': '../../Csvs/NFBC League Player File.csv',
    }

    for league, file_path in test_files.items():
        if os.path.exists(file_path):
            print(f"\n{'='*60}")
            print(f"Testing {league.upper()} Parser")
            print('='*60)

            try:
                players, detected_type = CSVParser.parse_csv(file_path)
                print(f"[OK] Detected: {detected_type}")
                print(f"[OK] Parsed {len(players)} players")
                print(f"\n[SAMPLE] Sample player:")
                print(players[0])

                # Count free agents vs owned
                free_agents = [p for p in players if p['owner'] == 'Free Agent']
                owned = [p for p in players if p['owner'] != 'Free Agent']
                print(f"\n[STATS] Stats:")
                print(f"  - Owned: {len(owned)}")
                print(f"  - Free Agents: {len(free_agents)}")

            except Exception as e:
                print(f"[FAIL] Error: {str(e)}")
        else:
            print(f"\n[WARN] File not found: {file_path}")
