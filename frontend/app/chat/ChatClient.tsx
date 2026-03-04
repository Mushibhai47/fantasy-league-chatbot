'use client';

import { useState, useEffect, useRef } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { sendChatMessage, getRoster, getFreeAgents, Player } from '@/lib/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function ChatClient() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const leagueId = searchParams.get('leagueId');
  const ownerName = searchParams.get('owner') || '';

  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hello! I\'m your fantasy baseball assistant. I have access to your roster and free agents. Use the quick action buttons below or ask me anything!',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [roster, setRoster] = useState<Player[]>([]);
  const [freeAgents, setFreeAgents] = useState<Player[]>([]);
  const [showRoster, setShowRoster] = useState(false);
  const [activeTab, setActiveTab] = useState<'today' | 'tomorrow' | 'weekly'>('today');
  const [teamNames, setTeamNames] = useState<string[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string>(ownerName || '');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!leagueId) {
      router.push('/');
      return;
    }

    // Load roster, free agents, and team names
    const loadData = async () => {
      try {
        const [rosterData, faData] = await Promise.all([
          getRoster(leagueId),
          getFreeAgents(leagueId),
        ]);
        setRoster(rosterData.players);
        setFreeAgents(faData.players);

        // Extract unique team names from roster
        const owners = new Set(rosterData.players.map((p: Player) => p.owner).filter((o: string) => o && o !== 'Free Agent'));
        setTeamNames(Array.from(owners).sort());
      } catch (err) {
        console.error('Error loading data:', err);
      }
    };

    loadData();
  }, [leagueId, router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Build conversation history from messages (last 6 for context)
  const getConversationHistory = () => {
    return messages.slice(-6).map((m) => ({
      role: m.role,
      content: m.content,
    }));
  };

  const sendMessage = async (messageText: string) => {
    if (!messageText.trim() || loading || !leagueId) return;

    setMessages((prev) => [...prev, { role: 'user', content: messageText }]);
    setLoading(true);

    try {
      const response = await sendChatMessage({
        league_id: leagueId,
        message: messageText,
        conversation_history: getConversationHistory(),
      });

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: response.response },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again.',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim()) return;
    const msg = input.trim();
    setInput('');
    await sendMessage(msg);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Quick action: sends a pre-built message
  const quickAction = (message: string) => {
    if (loading) return;
    sendMessage(message);
  };

  if (!leagueId) {
    return null;
  }

  // Build team identifier for quick actions
  const teamId = selectedTeam || ownerName || 'my team';

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-razzball-secondary text-white p-4 shadow-md">
        <div className="container mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">Fantasy Baseball Assistant</h1>
            <p className="text-sm text-white/80">
              {roster.length} players in roster {freeAgents.length > 0 && `\u2022 ${freeAgents.length} free agents`}
              {ownerName && ` \u2022 ${ownerName}`}
            </p>
          </div>
          <div className="flex gap-2 items-center">
            {teamNames.length > 0 && (
              <select
                value={selectedTeam}
                onChange={(e) => setSelectedTeam(e.target.value)}
                className="bg-white/20 text-white border border-white/30 rounded px-2 py-1 text-sm"
              >
                <option value="" className="text-gray-900">Select Team</option>
                {teamNames.map((t) => (
                  <option key={t} value={t} className="text-gray-900">{t}</option>
                ))}
              </select>
            )}
            <button
              onClick={() => setShowRoster(!showRoster)}
              className="btn-secondary"
            >
              {showRoster ? 'Hide' : 'Show'} Roster
            </button>
            <button
              onClick={() => router.push('/')}
              className="btn-secondary"
            >
              New Upload
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 container mx-auto p-4 flex gap-4">
        {/* Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Messages */}
          <div className="flex-1 bg-white rounded-lg shadow-md p-4 mb-4 overflow-y-auto max-h-[calc(100vh-340px)]">
            <div className="space-y-4">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-4 ${
                      message.role === 'user'
                        ? 'bg-razzball-primary text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    <p className="whitespace-pre-wrap text-sm font-mono">{message.content}</p>
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 rounded-lg p-4">
                    <div className="flex space-x-2">
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-100" />
                      <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-200" />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Quick Action Buttons */}
          <div className="bg-white rounded-lg shadow-md p-3 mb-3">
            {/* Tab Selector */}
            <div className="flex gap-1 mb-3">
              <button
                onClick={() => setActiveTab('today')}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  activeTab === 'today'
                    ? 'bg-razzball-primary text-white'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                }`}
              >
                Today
              </button>
              <button
                onClick={() => setActiveTab('tomorrow')}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  activeTab === 'tomorrow'
                    ? 'bg-razzball-primary text-white'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                }`}
              >
                Tomorrow
              </button>
              <button
                onClick={() => setActiveTab('weekly')}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  activeTab === 'weekly'
                    ? 'bg-razzball-primary text-white'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                }`}
              >
                Weekly
              </button>
            </div>

            {/* Action Buttons per Tab */}
            <div className="flex flex-wrap gap-2">
              {activeTab === 'today' && (
                <>
                  <button
                    onClick={() => quickAction(`today start/sit ${teamId}`)}
                    disabled={loading}
                    className="text-sm bg-green-100 hover:bg-green-200 text-green-800 px-3 py-1.5 rounded-lg transition-colors font-medium disabled:opacity-50"
                  >
                    Today Start/Sit
                  </button>
                  <button
                    onClick={() => quickAction('today pickups')}
                    disabled={loading}
                    className="text-sm bg-blue-100 hover:bg-blue-200 text-blue-800 px-3 py-1.5 rounded-lg transition-colors font-medium disabled:opacity-50"
                  >
                    Today Pickups
                  </button>
                </>
              )}
              {activeTab === 'tomorrow' && (
                <>
                  <button
                    onClick={() => quickAction(`tomorrow start/sit ${teamId}`)}
                    disabled={loading}
                    className="text-sm bg-green-100 hover:bg-green-200 text-green-800 px-3 py-1.5 rounded-lg transition-colors font-medium disabled:opacity-50"
                  >
                    Tomorrow Start/Sit
                  </button>
                  <button
                    onClick={() => quickAction('tomorrow pickups')}
                    disabled={loading}
                    className="text-sm bg-blue-100 hover:bg-blue-200 text-blue-800 px-3 py-1.5 rounded-lg transition-colors font-medium disabled:opacity-50"
                  >
                    Tomorrow Pickups
                  </button>
                </>
              )}
              {activeTab === 'weekly' && (
                <>
                  <button
                    onClick={() => quickAction(`weekly start/sit ${teamId}`)}
                    disabled={loading}
                    className="text-sm bg-green-100 hover:bg-green-200 text-green-800 px-3 py-1.5 rounded-lg transition-colors font-medium disabled:opacity-50"
                  >
                    Weekly Start/Sit
                  </button>
                  <button
                    onClick={() => quickAction('weekly pickups')}
                    disabled={loading}
                    className="text-sm bg-blue-100 hover:bg-blue-200 text-blue-800 px-3 py-1.5 rounded-lg transition-colors font-medium disabled:opacity-50"
                  >
                    Weekly Pickups
                  </button>
                </>
              )}
              {/* Always-visible buttons */}
              <button
                onClick={() => quickAction('league overview')}
                disabled={loading}
                className="text-sm bg-purple-100 hover:bg-purple-200 text-purple-800 px-3 py-1.5 rounded-lg transition-colors font-medium disabled:opacity-50"
              >
                League Overview
              </button>
              <button
                onClick={() => quickAction(`team overview ${teamId}`)}
                disabled={loading}
                className="text-sm bg-orange-100 hover:bg-orange-200 text-orange-800 px-3 py-1.5 rounded-lg transition-colors font-medium disabled:opacity-50"
              >
                My Team Overview
              </button>
            </div>
          </div>

          {/* Input Area */}
          <div className="bg-white rounded-lg shadow-md p-4">
            <div className="flex gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me about pickups, drops, or roster strategy..."
                className="input-field resize-none"
                rows={2}
                disabled={loading}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="btn-primary px-8"
              >
                Send
              </button>
            </div>
          </div>
        </div>

        {/* Roster Sidebar */}
        {showRoster && (
          <div className="w-96 bg-white rounded-lg shadow-md p-4 overflow-y-auto max-h-[calc(100vh-200px)]">
            <h2 className="text-xl font-bold mb-4">My Roster</h2>
            <div className="space-y-2">
              {roster.slice(0, 25).map((player, index) => (
                <div key={index} className="border-b border-gray-200 pb-2">
                  <div className="font-semibold">{player.name}</div>
                  <div className="text-sm text-gray-600">
                    {player.mlb_team} - {player.position}
                  </div>
                  {player.hr !== null && (
                    <div className="text-xs text-gray-500">
                      Proj: {player.hr} HR, {player.rbi} RBI, {player.sb} SB
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
