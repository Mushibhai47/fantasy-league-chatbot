"""Player Matching Service - Match CSV players to database using IDs or fuzzy matching"""
from sqlalchemy.orm import Session
from fuzzywuzzy import fuzz
from typing import Optional, Dict
from app.models import Player


class PlayerMatcher:
    """Match players from CSVs to database"""

    def __init__(self, db: Session):
        self.db = db

    def match_by_fantrax_id(self, fantrax_id: str) -> Optional[Player]:
        """Match player by Fantrax ID (*05ajh*)"""
        return self.db.query(Player).filter(Player.fantrax_id == fantrax_id).first()

    def match_by_nfbc_id(self, nfbc_id: int) -> Optional[Player]:
        """Match player by NFBC ID (11802)"""
        return self.db.query(Player).filter(Player.nfbc_id == nfbc_id).first()

    def match_by_razzball_id(self, razzball_id: int) -> Optional[Player]:
        """Match player by Razzball ID (RazzID)"""
        return self.db.query(Player).filter(Player.razzball_id == razzball_id).first()

    def match_by_name(
        self,
        name: str,
        mlb_team: Optional[str] = None,
        position: Optional[str] = None,
        threshold: int = 85
    ) -> Optional[Player]:
        """
        Match player by fuzzy name matching

        Args:
            name: Player name to match
            mlb_team: MLB team (BOS, NYY) - optional for better matching
            position: Position (SP, OF) - optional for better matching
            threshold: Minimum fuzzy match score (0-100)

        Returns:
            Matched Player or None
        """
        # Get all players (or filter by team/position if provided)
        query = self.db.query(Player)

        if mlb_team:
            query = query.filter(Player.team == mlb_team)

        if position:
            query = query.filter(Player.position.like(f'%{position}%'))

        candidates = query.all()

        if not candidates:
            # Try without filters
            candidates = self.db.query(Player).all()

        # Find best fuzzy match
        best_match = None
        best_score = 0

        for candidate in candidates:
            # CBS fuzzy match: verify first letter of MLB team matches to reduce false positives
            if mlb_team and candidate.team:
                if mlb_team[0].upper() != candidate.team[0].upper():
                    continue

            # Try different name variations
            scores = [
                fuzz.ratio(name.lower(), candidate.name.lower()),
                fuzz.partial_ratio(name.lower(), candidate.name.lower()),
                fuzz.token_sort_ratio(name.lower(), candidate.name.lower()),
            ]
            score = max(scores)

            if score > best_score:
                best_score = score
                best_match = candidate

        # Return match if above threshold
        if best_score >= threshold:
            return best_match

        return None

    def match_player(self, player_data: Dict) -> Optional[Player]:
        """
        Smart matching - try ID first, then fuzzy name

        Args:
            player_data: Dict with keys: fantrax_id, nfbc_id, name, mlb_team, position

        Returns:
            Matched Player or None
        """
        # Try Fantrax ID first
        if player_data.get('fantrax_id'):
            match = self.match_by_fantrax_id(player_data['fantrax_id'])
            if match:
                return match

        # Try NFBC ID
        if player_data.get('nfbc_id'):
            match = self.match_by_nfbc_id(player_data['nfbc_id'])
            if match:
                return match

        # Fallback to fuzzy name matching
        name = player_data.get('name')
        if name:
            match = self.match_by_name(
                name=name,
                mlb_team=player_data.get('mlb_team'),
                position=player_data.get('position')
            )
            if match:
                return match

        return None

    def get_or_create_player(self, player_data: Dict) -> Player:
        """
        Try to match existing player, or create new one if not found

        Args:
            player_data: Dict with player info

        Returns:
            Player (existing or newly created)
        """
        # Try to match first
        player = self.match_player(player_data)

        if player:
            # Update IDs if we have new ones
            if player_data.get('fantrax_id') and not player.fantrax_id:
                player.fantrax_id = player_data['fantrax_id']
            if player_data.get('nfbc_id') and not player.nfbc_id:
                player.nfbc_id = player_data['nfbc_id']
            self.db.commit()
            return player

        # Create new player if no match
        new_player = Player(
            name=player_data['name'],
            team=player_data.get('mlb_team'),
            position=player_data.get('position'),
            fantrax_id=player_data.get('fantrax_id'),
            nfbc_id=player_data.get('nfbc_id'),
        )
        self.db.add(new_player)
        self.db.commit()
        self.db.refresh(new_player)

        return new_player


# Test the matcher
if __name__ == "__main__":
    from app.database import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    matcher = PlayerMatcher(db)

    # Test data
    test_players = [
        {"name": "Aaron Judge", "mlb_team": "NYY", "position": "OF"},
        {"name": "Shohei Ohtani", "mlb_team": "LAD", "position": "DH"},
        {"fantrax_id": "*05ajh*", "name": "Garrett Crochet"},
        {"nfbc_id": 11802, "name": "Andrew Abbott"},
    ]

    print("\n🧪 Testing Player Matcher\n")

    for test_player in test_players:
        print(f"Testing: {test_player}")
        match = matcher.match_player(test_player)

        if match:
            print(f"  ✅ Matched: {match.name} (ID: {match.id}, RazzID: {match.razzball_id})")
        else:
            print(f"  ❌ No match found")

    db.close()
