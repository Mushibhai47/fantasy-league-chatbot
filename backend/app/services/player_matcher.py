"""Player Matching Service - Match CSV players to database using IDs or fuzzy matching"""
from sqlalchemy.orm import Session
from fuzzywuzzy import fuzz
from typing import Optional, Dict, List
from app.models import Player


class PlayerMatcher:
    """Match players from CSVs to database.

    Loads all existing players from the DB into memory once (per matcher instance)
    so that fuzzy-matching 4 000+ CBS players doesn't require thousands of DB round-trips.
    """

    def __init__(self, db: Session):
        self.db = db
        # Lazily populated by _ensure_cache()
        self._all_players: Optional[List[Player]] = None
        self._cbs_name_index: Dict[str, Player] = {}
        self._fantrax_id_index: Dict[str, Player] = {}
        self._nfbc_id_index: Dict[int, Player] = {}
        self._yahoo_id_index: Dict[str, Player] = {}

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _ensure_cache(self):
        """Load all players from DB into memory (once per upload session)."""
        if self._all_players is not None:
            return
        self._all_players = self.db.query(Player).all()
        self._cbs_name_index = {
            p.cbs_player_name: p for p in self._all_players if p.cbs_player_name
        }
        self._fantrax_id_index = {
            p.fantrax_id: p for p in self._all_players if p.fantrax_id
        }
        self._nfbc_id_index = {
            p.nfbc_id: p for p in self._all_players if p.nfbc_id
        }
        self._yahoo_id_index = {
            p.yahoo_id: p for p in self._all_players if p.yahoo_id
        }

    def _add_to_cache(self, player: Player):
        """Register a newly-created player in the ID indexes only.

        We intentionally do NOT append to _all_players (the fuzzy-match pool).
        Adding every new player there would cause O(n²) fuzzy comparisons during
        a 4000-player CBS upload on a fresh DB — new CBS players can't sensibly
        match each other via fuzzy name anyway.
        """
        if player.cbs_player_name:
            self._cbs_name_index[player.cbs_player_name] = player
        if player.fantrax_id:
            self._fantrax_id_index[player.fantrax_id] = player
        if player.nfbc_id:
            self._nfbc_id_index[player.nfbc_id] = player
        if player.yahoo_id:
            self._yahoo_id_index[player.yahoo_id] = player

    # ------------------------------------------------------------------
    # ID lookups (in-memory after first call)
    # ------------------------------------------------------------------

    def match_by_fantrax_id(self, fantrax_id: str) -> Optional[Player]:
        """Match player by Fantrax ID (*05ajh*)"""
        self._ensure_cache()
        return self._fantrax_id_index.get(fantrax_id)

    def match_by_nfbc_id(self, nfbc_id: int) -> Optional[Player]:
        """Match player by NFBC ID (11802)"""
        self._ensure_cache()
        return self._nfbc_id_index.get(nfbc_id)

    def match_by_razzball_id(self, razzball_id: int) -> Optional[Player]:
        """Match player by Razzball ID (RazzID) — still uses DB (less frequent)"""
        return self.db.query(Player).filter(Player.razzball_id == razzball_id).first()

    def match_by_cbs_name(self, cbs_player_name: str) -> Optional[Player]:
        """Match player by CBS player name (e.g., 'Aaron Judge OF | NYY')"""
        self._ensure_cache()
        return self._cbs_name_index.get(cbs_player_name)

    # ------------------------------------------------------------------
    # Fuzzy name matching (in-memory)
    # ------------------------------------------------------------------

    def match_by_name(
        self,
        name: str,
        mlb_team: Optional[str] = None,
        position: Optional[str] = None,
        threshold: int = 85
    ) -> Optional[Player]:
        """
        Match player by fuzzy name matching (runs entirely in Python memory).

        Args:
            name: Player name to match
            mlb_team: MLB team (BOS, NYY) - optional for better matching
            position: Position (SP, OF) - optional for better matching
            threshold: Minimum fuzzy match score (0-100)
        """
        self._ensure_cache()
        candidates = self._all_players

        if not candidates:
            return None

        # Narrow candidate list if team/position are supplied
        if mlb_team:
            team_candidates = [p for p in candidates if p.team == mlb_team]
            if not team_candidates:
                team_candidates = candidates  # fall back to all
        else:
            team_candidates = candidates

        if position:
            pos_candidates = [
                p for p in team_candidates
                if p.position and position in p.position
            ]
            if not pos_candidates:
                pos_candidates = team_candidates  # fall back

        else:
            pos_candidates = team_candidates

        # Find best fuzzy match
        best_match = None
        best_score = 0

        for candidate in pos_candidates:
            # CBS fuzzy match: verify first letter of MLB team matches
            if mlb_team and candidate.team:
                if mlb_team[0].upper() != candidate.team[0].upper():
                    continue

            scores = [
                fuzz.ratio(name.lower(), candidate.name.lower()),
                fuzz.partial_ratio(name.lower(), candidate.name.lower()),
                fuzz.token_sort_ratio(name.lower(), candidate.name.lower()),
            ]
            score = max(scores)

            if score > best_score:
                best_score = score
                best_match = candidate

        return best_match if best_score >= threshold else None

    # ------------------------------------------------------------------
    # Smart match (ID first, then name)
    # ------------------------------------------------------------------

    def match_player(self, player_data: Dict) -> Optional[Player]:
        """
        Smart matching - try ID first, then fuzzy name.
        """
        if player_data.get('yahoo_id'):
            self._ensure_cache()
            match = self._yahoo_id_index.get(player_data['yahoo_id'])
            if match:
                return match

        if player_data.get('fantrax_id'):
            match = self.match_by_fantrax_id(player_data['fantrax_id'])
            if match:
                return match

        if player_data.get('nfbc_id'):
            match = self.match_by_nfbc_id(player_data['nfbc_id'])
            if match:
                return match

        name = player_data.get('name')
        if name:
            is_cbs_only = (
                player_data.get('cbs_player_name') and
                not player_data.get('fantrax_id') and
                not player_data.get('nfbc_id')
            )
            name_threshold = 92 if is_cbs_only else 85
            match = self.match_by_name(
                name=name,
                mlb_team=player_data.get('mlb_team'),
                position=player_data.get('position'),
                threshold=name_threshold,
            )
            if match:
                return match

        return None

    # ------------------------------------------------------------------
    # Get or create
    # ------------------------------------------------------------------

    def get_or_create_player(self, player_data: Dict) -> Player:
        """
        Try to match existing player, or create new one if not found.
        Uses db.flush() instead of db.commit() so the caller can batch-commit.
        """
        player = self.match_player(player_data)

        # Also try CBS name if provided
        if not player and player_data.get('cbs_player_name'):
            candidate = self.match_by_cbs_name(player_data['cbs_player_name'])
            if candidate:
                provided_name = player_data.get('name', '')
                name_similarity = fuzz.ratio(provided_name.lower(), candidate.name.lower())
                if name_similarity >= 75:
                    player = candidate
                else:
                    # Clear the incorrect CBS name from the wrong player
                    candidate.cbs_player_name = None
                    # Remove from index too
                    old_key = player_data.get('cbs_player_name')
                    if old_key and self._cbs_name_index.get(old_key) is candidate:
                        del self._cbs_name_index[old_key]

        if player:
            # Update IDs / names if we have new ones
            if player_data.get('yahoo_id') and not player.yahoo_id:
                player.yahoo_id = player_data['yahoo_id']
                self._yahoo_id_index[player.yahoo_id] = player
            if player_data.get('fantrax_id') and not player.fantrax_id:
                player.fantrax_id = player_data['fantrax_id']
                self._fantrax_id_index[player.fantrax_id] = player
            if player_data.get('nfbc_id') and not player.nfbc_id:
                player.nfbc_id = player_data['nfbc_id']
                self._nfbc_id_index[player.nfbc_id] = player
            if player_data.get('cbs_player_name') and not player.cbs_player_name:
                player.cbs_player_name = player_data['cbs_player_name']
                self._cbs_name_index[player.cbs_player_name] = player
            # Fix legacy "Last, First" NFBC names
            new_name = player_data.get('name', '')
            if ',' in player.name and new_name and ',' not in new_name:
                player.name = new_name
            if player_data.get('position') and not player.position:
                player.position = player_data['position']
            # No commit here — caller does a single commit at the end
            return player

        # Create new player (no flush here — caller does a single db.flush() after the loop)
        new_player = Player(
            name=player_data['name'],
            team=player_data.get('mlb_team'),
            position=player_data.get('position'),
            fantrax_id=player_data.get('fantrax_id'),
            nfbc_id=player_data.get('nfbc_id'),
            cbs_player_name=player_data.get('cbs_player_name'),
            yahoo_id=player_data.get('yahoo_id'),
        )
        self.db.add(new_player)
        self._add_to_cache(new_player)
        return new_player
