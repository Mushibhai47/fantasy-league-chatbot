'use client';

import { useState, useEffect, useRef } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { sendChatMessage, getRoster, getFreeAgents, Player } from '@/lib/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function ChatPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const leagueId = searchParams.get('leagueId');

  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hello! I\'m your fantasy baseball assistant. I have access to your roster and free agents. Ask me anything about pickups, drops, or roster strategy!',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [roster, setRoster] = useState<Player[]>([]);
  const [freeAgents, setFreeAgents] = useState<Player[]>([]);
  const [showRoster, setShowRoster] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!leagueId) {
      router.push('/');
      return;
    }

    // Load roster and free agents
    const loadData = async () => {
      try {
        const [rosterData, faData] = await Promise.all([
          getRoster(leagueId),
          getFreeAgents(leagueId),
        ]);
        setRoster(rosterData.players);
        setFreeAgents(faData.players);
      } catch (err) {
        console.error('Error loading data:', err);
      }
    };

    loadData();
  }, [leagueId, router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading || !leagueId) return;

    const userMessage = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const response = await sendChatMessage({
        league_id: leagueId,
        message: userMessage,
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

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!leagueId) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-razzball-secondary text-white p-4 shadow-md">
        <div className="container mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">Fantasy Baseball Assistant</h1>
            <p className="text-sm text-white/80">
              {roster.length} players in roster • {freeAgents.length} free agents
            </p>
          </div>
          <div className="flex gap-2">
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
          <div className="flex-1 bg-white rounded-lg shadow-md p-4 mb-4 overflow-y-auto max-h-[calc(100vh-250px)]">
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
                    <p className="whitespace-pre-wrap">{message.content}</p>
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

            {/* Suggested Questions */}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={() => setInput('Who should I pick up for home runs?')}
                className="text-sm bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded-full transition-colors"
              >
                Who should I pick up for HR?
              </button>
              <button
                onClick={() => setInput('Show me the top free agent pitchers')}
                className="text-sm bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded-full transition-colors"
              >
                Top free agent pitchers
              </button>
              <button
                onClick={() => setInput('What are my roster weaknesses?')}
                className="text-sm bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded-full transition-colors"
              >
                Roster weaknesses
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
