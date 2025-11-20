"""
Pupfi dApp Schemas

Each class corresponds to a MongoDB collection (lowercased class name).
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

class PupfiUser(BaseModel):
    username: str = Field(..., min_length=3, max_length=24)
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    wallet_address: Optional[str] = Field(None, description="Linked on-chain address")
    session_public_key: Optional[str] = Field(None, description="Ephemeral session wallet public key")
    balance: int = Field(0, ge=0, description="Off-chain token balance for gameplay rewards")
    xp: int = 0
    level: int = 1
    referral_code: Optional[str] = None
    referred_by: Optional[str] = None
    streak_days: int = 0
    last_login_at: Optional[datetime] = None
    badges: List[str] = []

class Game(BaseModel):
    key: str = Field(..., description="Unique game key, e.g., 'pup-sprint'")
    name: str
    description: str
    max_players: int = 2
    rules: Dict[str, str] = {}

class Match(BaseModel):
    game_key: str
    creator_id: str
    status: str = Field("waiting", description="waiting, active, finished, cancelled")
    players: List[str] = []
    scores: Dict[str, int] = {}
    winner_id: Optional[str] = None
    reward: int = 0
    seed: int = 0
    server_commit: Optional[str] = None
    server_secret: Optional[str] = None
    client_reveal: Optional[str] = None
    final_seed: Optional[int] = None
    tips_total: int = 0

class Leaderboard(BaseModel):
    game_key: str
    user_id: str
    score: int
    username: str

class Quest(BaseModel):
    key: str
    title: str
    description: str
    reward: int = 0
    type: str = Field("daily", description="daily, weekly, special")

class Claim(BaseModel):
    user_id: str
    quest_key: str
    claimed_at: datetime

class Transaction(BaseModel):
    user_id: str
    amount: int
    type: str = Field(..., description="earn, spend, transfer_in, transfer_out")
    reason: str = ""

class StakingPool(BaseModel):
    key: str
    name: str
    total_staked: int = 0
    participants: Dict[str, int] = {}

class Badge(BaseModel):
    user_id: str
    key: str
    title: str
    minted_at: datetime = Field(default_factory=datetime.utcnow)
