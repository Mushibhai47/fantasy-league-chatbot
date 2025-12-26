import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface LeagueResponse {
  id: string;
  league_type: string;
  total_players: number;
  owned_players: number;
  free_agents: number;
  uploaded_at: string;
}

export interface Player {
  id: number;
  name: string;
  mlb_team: string | null;
  position: string | null;
  owner: string;
  hr: number | null;
  rbi: number | null;
  sb: number | null;
  avg: number | null;
}

export interface RosterResponse {
  league_id: string;
  league_type: string;
  players: Player[];
}

export interface ChatRequest {
  league_id: string;
  message: string;
}

export interface ChatResponse {
  message: string;
  response: string;
  tokens_used: number;
}

// Upload CSV file
export async function uploadCSV(file: File): Promise<LeagueResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await axios.post(`${API_URL}/api/csv/upload`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
}

// Get roster for a league
export async function getRoster(leagueId: string, owner?: string): Promise<RosterResponse> {
  const params = owner ? { owner } : {};
  const response = await axios.get(`${API_URL}/api/csv/${leagueId}/roster`, { params });
  return response.data;
}

// Get free agents
export async function getFreeAgents(leagueId: string): Promise<RosterResponse> {
  const response = await axios.get(`${API_URL}/api/csv/${leagueId}/free-agents`);
  return response.data;
}

// Chat with AI
export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await axios.post(`${API_URL}/api/chat/`, request);
  return response.data;
}
