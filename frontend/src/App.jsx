import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { 
  Send, 
  Sparkles, 
  ChevronDown, 
  ChevronUp, 
  Terminal, 
  CheckCircle2, 
  AlertCircle,
  FileSearch,
  Compass,
  GraduationCap,
  Network,
  LogOut,
  Upload,
  User
} from 'lucide-react';
import './App.css';

const agentInfo = {
  profile_scanner: {
    label: "Profile Scanner",
    icon: FileSearch,
    themeClass: "scanner"
  },
  market_scout: {
    label: "Market Scout",
    icon: Compass,
    themeClass: "scout"
  },
  academic_architect: {
    label: "Academic Architect",
    icon: GraduationCap,
    themeClass: "architect"
  }
};

const ToolCallWidget = ({ toolName, input, output, status }) => {
  const [expanded, setExpanded] = useState(true);
  const info = agentInfo[toolName] || {
    label: toolName,
    icon: Terminal,
    themeClass: "default"
  };
  const Icon = info.icon;

  return (
    <div className={`tool-call-widget ${info.themeClass}`}>
      <div className="tool-call-header" onClick={() => setExpanded(!expanded)}>
        <div className="tool-title">
          <Icon size={16} />
          <span>{info.label}</span>
        </div>
        <div className="tool-status">
          {status === 'running' && (
            <div className="tool-status running">
              <div className="spinner" />
              <span>Running...</span>
            </div>
          )}
          {status === 'completed' && (
            <div className="tool-status completed">
              <CheckCircle2 size={14} style={{ color: 'var(--primary)' }} />
              <span>Finished</span>
            </div>
          )}
          {status === 'error' && (
            <div className="tool-status error">
              <AlertCircle size={14} style={{ color: 'red' }} />
              <span>Failed</span>
            </div>
          )}
          {expanded ? <ChevronUp size={16} style={{ marginLeft: 6 }} /> : <ChevronDown size={16} style={{ marginLeft: 6 }} />}
        </div>
      </div>
      
      {expanded && (
        <div className="tool-content">
          {input && (
            <div style={{ marginBottom: output ? '0.75rem' : 0 }}>
              <div className="tool-section-title">Agent Inputs</div>
              <pre className="tool-json">{JSON.stringify(input, null, 2)}</pre>
            </div>
          )}
          {output && (
            <div>
              <div className="tool-section-title">Agent Output Logs</div>
              <pre className="tool-json">{JSON.stringify(output, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const SUGGESTED_QUESTIONS = [
  {
    title: "1. Scan Profile",
    desc: "Assess background details to determine skill fits",
    prompt: "Please scan my profile: I am a self-taught programmer with 1 year of HTML/CSS experience, basic JavaScript knowledge, and want to become a professional Frontend Engineer."
  },
  {
    title: "2. Scout Market",
    desc: "Explore job trends, requirements, and salaries",
    prompt: "I want to explore the market for Python Backend Developers. What are the current industry demands, salary expectations, and top required frameworks?"
  },
  {
    title: "3. Architect Learning Path",
    desc: "Generate academic steps to fill target gaps",
    prompt: "I want to become a Cloud DevOps Engineer. My current skills are Linux administration and basic Python scripting. Can you architect a roadmap of courses and skills for me?"
  },
  {
    title: "4. Full Guidance",
    desc: "Activate all agents (Scan, Scout, Architect)",
    prompt: "Review my profile as an Entry-Level Data Analyst. My current experience is SQL queries and Excel modeling. Scan my background, scout the job market, and architect a learning roadmap."
  }
];

export default function App() {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('z_mentor_user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [googleClientId, setGoogleClientId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [activeAgents, setActiveAgents] = useState([]);
  const [backendUrl, setBackendUrl] = useState('http://localhost:8000');

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize input textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [inputValue]);

  // Fetch Google Client ID configuration from backend
  useEffect(() => {
    if (!user) {
      fetch(`${backendUrl}/auth/config`)
        .then(res => res.json())
        .then(data => {
          if (data.google_client_id) {
            setGoogleClientId(data.google_client_id);
          }
        })
        .catch(err => console.error("Failed to load Google Client ID config", err));
    }
  }, [user, backendUrl]);

  // Handle Google OAuth initialization
  useEffect(() => {
    if (!user && googleClientId && window.google?.accounts?.id) {
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: handleGoogleLoginResponse
      });
      
      const btnParent = document.getElementById("google-signin-button");
      if (btnParent) {
        window.google.accounts.id.renderButton(btnParent, {
          theme: "outline",
          size: "large",
          width: "100%"
        });
      }
    }
  }, [user, googleClientId]);

  const handleGoogleLoginResponse = async (response) => {
    setAuthLoading(true);
    try {
      const res = await fetch(`${backendUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: response.credential
        })
      });
      if (!res.ok) throw new Error("Google login verification failed");
      const userData = await res.json();
      localStorage.setItem('z_mentor_user', JSON.stringify(userData));
      setUser(userData);
    } catch (e) {
      console.error(e);
      alert("Authentication failed. Please verify the orchestrator connection.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('z_mentor_user');
    setUser(null);
    setMessages([]);
  };

  const handleAvatarClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Verify file is image
    if (!file.type.startsWith('image/')) {
      alert("Please upload an image file.");
      return;
    }

    const reader = new FileReader();
    reader.onloadend = async () => {
      const base64String = reader.result;
      try {
        const res = await fetch(`${backendUrl}/auth/upload-avatar`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            google_id: user.google_id,
            avatar_base64: base64String
          })
        });
        if (!res.ok) throw new Error("Image upload failed");
        const updatedUser = await res.json();
        localStorage.setItem('z_mentor_user', JSON.stringify(updatedUser));
        setUser(updatedUser);
      } catch (err) {
        console.error(err);
        alert("Failed to save profile picture to backend.");
      }
    };
    reader.readAsDataURL(file);
  };

  const handleSendMessage = async (textToSend) => {
    const query = textToSend || inputValue;
    if (!query.trim() || isLoading) return;

    if (!textToSend) {
      setInputValue('');
    }

    const userMessageId = 'user-' + Date.now();
    const assistantMessageId = 'assistant-' + Date.now();

    // Add user message
    const userMsg = { id: userMessageId, role: 'user', content: query };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    // Add an empty assistant message
    const assistantMsg = { id: assistantMessageId, role: 'assistant', content: '', toolCalls: [] };
    setMessages(prev => [...prev, assistantMsg]);

    try {
      const response = await fetch(`${backendUrl}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // Keep partial line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            const dataStr = trimmed.slice(6);
            try {
              const data = JSON.parse(dataStr);
              
              if (data.type === 'tool_start') {
                setActiveAgents(prev => [...new Set([...prev, data.tool])]);
                setMessages(prev => prev.map(msg => {
                  if (msg.id === assistantMessageId) {
                    const exists = msg.toolCalls.some(tc => tc.name === data.tool);
                    if (exists) return msg;
                    return {
                      ...msg,
                      toolCalls: [...msg.toolCalls, {
                        id: `${data.tool}-${Date.now()}`,
                        name: data.tool,
                        input: data.input,
                        status: 'running'
                      }]
                    };
                  }
                  return msg;
                }));
              } 
              else if (data.type === 'tool_end') {
                setActiveAgents(prev => prev.filter(t => t !== data.tool));
                setMessages(prev => prev.map(msg => {
                  if (msg.id === assistantMessageId) {
                    return {
                      ...msg,
                      toolCalls: msg.toolCalls.map(tc => {
                        if (tc.name === data.tool) {
                          return { ...tc, output: data.output, status: 'completed' };
                        }
                        return tc;
                      })
                    };
                  }
                  return msg;
                }));
              }
              else if (data.type === 'token') {
                setMessages(prev => prev.map(msg => {
                  if (msg.id === assistantMessageId) {
                    return { ...msg, content: msg.content + data.content };
                  }
                  return msg;
                }));
              }
              else if (data.type === 'error') {
                setMessages(prev => prev.map(msg => {
                  if (msg.id === assistantMessageId) {
                    return { ...msg, content: msg.content + `\n\n*Agent Error: ${data.content}*` };
                  }
                  return msg;
                }));
              }
            } catch (e) {
              console.error("Error parsing JSON chunk:", dataStr, e);
            }
          }
        }
      }
    } catch (error) {
      console.error("Streaming error:", error);
      setMessages(prev => prev.map(msg => {
        if (msg.id === assistantMessageId) {
          return { 
            ...msg, 
            content: msg.content 
              ? msg.content + `\n\n*Connection error: ${error.message}*`
              : `Unable to connect to orchestrator at ${backendUrl}. Make sure the backend server is running and CORS is enabled.`
          };
        }
        return msg;
      }));
    } finally {
      setIsLoading(false);
      setActiveAgents([]);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Render Login Screen if user is not authenticated
  if (!user) {
    return (
      <div className="login-screen">
        <div className="login-card">
          <div className="login-logo">
            <Sparkles size={32} />
          </div>
          <h1 className="login-title">Z-MentorAI</h1>
          <p className="login-subtitle">Navigate Your Career with Specialized AI Co-pilots</p>
          
          <div className="login-actions">
            {/* Google Sign In container */}
            <div id="google-signin-button" className="google-btn-container"></div>
          </div>
        </div>
      </div>
    );
  }

  // Get current avatar image (uploaded custom avatar or default google photo or user icon)
  const avatarSrc = user.custom_avatar || user.picture;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-logo">
            <Sparkles size={20} />
          </div>
          <div>
            <h1 className="brand-title">Z-MentorAI</h1>
          </div>
        </div>

        {/* Specialized Agent Badges */}
        <div className="agent-status-bar">
          <div className={`agent-badge ${activeAgents.includes('profile_scanner') ? 'active' : ''}`}>
            <div className="badge-dot" />
            <span>Profile Scanner</span>
          </div>
          <div className={`agent-badge ${activeAgents.includes('market_scout') ? 'active' : ''}`}>
            <div className="badge-dot" />
            <span>Market Scout</span>
          </div>
          <div className={`agent-badge ${activeAgents.includes('academic_architect') ? 'active' : ''}`}>
            <div className="badge-dot" />
            <span>Academic Architect</span>
          </div>
        </div>

        {/* User Identity Panel */}
        <div className="user-profile-section">
          <div className="avatar-wrapper" onClick={handleAvatarClick} title="Upload custom profile picture">
            {avatarSrc ? (
              <img src={avatarSrc} alt="User avatar" className="user-avatar" />
            ) : (
              <div className="user-avatar-placeholder">
                <User size={18} />
              </div>
            )}
            <div className="avatar-hover-overlay">
              <Upload size={14} />
            </div>
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileChange} 
              style={{ display: 'none' }} 
              accept="image/*" 
            />
          </div>
          <div className="user-info">
            <div className="user-name">{user.name}</div>
            <div className="user-email">{user.email}</div>
          </div>
          <button className="logout-btn" onClick={handleLogout} title="Log Out">
            <LogOut size={16} />
          </button>
        </div>
      </header>

      {/* Main Panel */}
      <main className="chat-main">
        <div className="chat-area">
          {messages.length === 0 ? (
            /* Welcome / Suggested Questions Page */
            <div className="welcome-container">
              <div className="welcome-logo">
                <Network size={32} />
              </div>
              <h2 className="welcome-title">Empower Your Career Journey, {user.name.split(' ')[0]}</h2>
              <p className="welcome-subtitle">
                Z-MentorAI links specialized agents to scan your profile, scout market demands, and architect customized learning roadmaps.
              </p>
              
              <div className="suggested-questions">
                {SUGGESTED_QUESTIONS.map((q, idx) => (
                  <div 
                    key={idx} 
                    className="suggested-card"
                    onClick={() => handleSendMessage(q.prompt)}
                  >
                    <div className="suggested-card-title">{q.title}</div>
                    <div className="suggested-card-desc">{q.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* Active Messages Feed */
            <div className="messages-feed">
              {messages.map((msg) => (
                <div key={msg.id} className={`message-wrapper ${msg.role}`}>
                  <div className="message-header">
                    {msg.role === 'user' ? 'You' : 'Orchestrator'}
                  </div>
                  
                  {/* Render Agent trace elements first inside assistant messages */}
                  {msg.role === 'assistant' && msg.toolCalls && msg.toolCalls.map((tc) => (
                    <ToolCallWidget 
                      key={tc.id}
                      toolName={tc.name}
                      input={tc.input}
                      output={tc.output}
                      status={tc.status}
                    />
                  ))}

                  {/* Message Bubble Text */}
                  {(msg.content || msg.role === 'user') && (
                    <div className="message-bubble">
                      {msg.role === 'user' ? (
                        <p>{msg.content}</p>
                      ) : (
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {/* Thinking dots while generating (only if no tokens generated yet and no tools running) */}
              {isLoading && activeAgents.length === 0 && (
                <div className="thinking-wrapper">
                  <span>Synthesizing response</span>
                  <div className="thinking-dots">
                    <div className="thinking-dot" />
                    <div className="thinking-dot" />
                    <div className="thinking-dot" />
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          )}

          {/* Input Panel */}
          <div className="input-panel">
            <div className="input-container">
              <textarea
                ref={textareaRef}
                className="chat-input"
                placeholder="Ask Z-MentorAI anything..."
                rows={1}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
              />
              <button 
                className="send-button"
                onClick={() => handleSendMessage()}
                disabled={isLoading || !inputValue.trim()}
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
