import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Compass,
  FileText,
  FileSearch,
  GraduationCap,
  LogOut,
  MessageSquare,
  Network,
  Paperclip,
  Plus,
  Send,
  Sparkles,
  Terminal,
  Trash2,
  Upload,
  User,
  X
} from 'lucide-react';
import './App.css';

const acceptedCvMimeTypes = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
]);

const acceptedCvExtensions = ['pdf', 'docx'];
const maxCvFileSizeBytes = 10 * 1024 * 1024;

function formatFileSize(bytes) {
  if (!bytes) return '0 KB';
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileExtension(filename) {
  return filename.split('.').pop()?.toLowerCase() || '';
}

const agentInfo = {
  profile_scanner: {
    label: 'Quét Hồ Sơ',
    description: 'Tóm tắt điểm mạnh, kỹ năng và tín hiệu phù hợp từ hồ sơ của bạn.',
    icon: FileSearch,
    themeClass: 'scanner',
    accent: '#2ce8d4'
  },
  market_scout: {
    label: 'Khảo Sát Thị Trường',
    description: 'Đọc nhu cầu tuyển dụng, xu hướng vai trò và tín hiệu đãi ngộ.',
    icon: Compass,
    themeClass: 'scout',
    accent: '#a78bfa'
  },
  academic_architect: {
    label: 'Lộ Trình Học Tập',
    description: 'Biến khoảng trống kỹ năng thành lộ trình học tập thực tế.',
    icon: GraduationCap,
    themeClass: 'architect',
    accent: '#f8c96b'
  },
  academic_architect_input_verifier: {
    label: 'Xác Nhận Đầu Vào',
    description: 'Kiểm tra kỹ năng và mục tiêu trước khi lập lộ trình.',
    icon: GraduationCap,
    themeClass: 'architect',
    accent: '#f8c96b'
  }
};

const suggestedQuestions = [
  {
    agent: 'profile_scanner',
    title: 'Quét hồ sơ',
    desc: 'Đánh giá nền tảng hiện tại và độ phù hợp kỹ năng',
    prompt: 'Hãy quét hồ sơ của tôi: tôi tự học lập trình, có 1 năm kinh nghiệm HTML/CSS, biết JavaScript cơ bản và muốn trở thành Frontend Engineer chuyên nghiệp.'
  },
  {
    agent: 'profile_scanner',
    title: 'Holland Test',
    desc: 'Kiểm tra nhóm RIASEC và gợi ý hướng nghề phù hợp',
    prompt: 'Tôi muốn làm Holland Test / RIASEC để xem nhóm nghề nghiệp nào phù hợp với tôi.'
  },
  {
    agent: 'market_scout',
    title: 'Khảo sát thị trường',
    desc: 'Tìm hiểu xu hướng tuyển dụng, yêu cầu và mức lương',
    prompt: 'Tôi muốn khảo sát thị trường cho vị trí Python Backend Developer. Hiện tại nhu cầu tuyển dụng, kỳ vọng lương và các framework quan trọng nhất là gì?'
  },
  {
    agent: 'academic_architect',
    title: 'Dựng lộ trình học',
    desc: 'Tạo các bước học để lấp khoảng trống mục tiêu',
    prompt: 'Tôi muốn xây dựng lộ trình học tập.'
  },
  {
    agent: 'profile_scanner',
    title: 'Tư vấn tổng hợp',
    desc: 'Kích hoạt tất cả agent để kiểm tra định hướng từ đầu đến cuối',
    prompt: 'Hãy đánh giá hồ sơ của tôi cho vị trí Entry-Level Data Analyst. Kinh nghiệm hiện tại của tôi gồm truy vấn SQL và dựng mô hình Excel. Hãy quét nền tảng, khảo sát thị trường và thiết kế lộ trình học cho tôi.'
  }
];

function LoginChatTerminal() {
  return (
    <aside className="login-terminal" aria-label="Bản xem trước cuộc trò chuyện Z-MentorAI">
      <div className="terminal-topbar">
        <div className="terminal-window-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <span className="terminal-label">mentor.session</span>
      </div>
      <div className="terminal-body">
        <div className="terminal-line user-line">
          <span className="terminal-prompt">$ bạn</span>
          <p>Hãy quét CV của tôi cho vị trí Junior Data Analyst.</p>
        </div>
        <div className="terminal-line ai-line">
          <span className="terminal-prompt">z-mentor</span>
          <p>Agent Quét Hồ Sơ thấy tín hiệu SQL khá tốt, nhưng CV cần làm rõ tác động dự án và bằng chứng dashboard.</p>
        </div>
        <div className="terminal-line ai-line">
          <span className="terminal-prompt">thị trường</span>
          <p>Các vị trí đầu vào thường yêu cầu Excel, SQL, BI tools và một bài phân tích trong portfolio.</p>
        </div>
        <div className="terminal-command">
          <span>$</span>
          <span className="terminal-caret">dựng lộ trình</span>
        </div>
      </div>
    </aside>
  );
}

function normalizeToolOutput(output) {
  if (!output) return null;
  if (Array.isArray(output)) {
    const textPart = output.find((part) => typeof part?.text === 'string');
    return textPart ? normalizeToolOutput(textPart.text) : null;
  }
  if (typeof output === 'object') return output;
  if (typeof output !== 'string') return null;

  try {
    return JSON.parse(output);
  } catch {
    const jsonMatch = output.match(/\{[\s\S]*\}/);
    if (!jsonMatch) return null;
    try {
      return JSON.parse(jsonMatch[0]);
    } catch {
      return null;
    }
  }
}

function normalizeStoredToolCalls(toolCalls = []) {
  if (!Array.isArray(toolCalls)) return [];

  return toolCalls.map((toolCall, index) => ({
    id: toolCall.id || `${toolCall.name || toolCall.tool || 'tool'}-${index}`,
    name: toolCall.name || toolCall.tool,
    input: toolCall.input,
    output: toolCall.output,
    status: toolCall.status || 'completed'
  })).filter((toolCall) => toolCall.name);
}

function hasHollandInteractiveToolCall(toolCalls = []) {
  return toolCalls.some((toolCall) => {
    const output = normalizeToolOutput(toolCall.output);
    return output?.feature === 'holland_assessment'
      && (output?.questions || output?.top_code);
  });
}

function getVisibleToolCalls(toolCalls = []) {
  const hasSuccessfulHollandResult = toolCalls.some((toolCall) => {
    const output = normalizeToolOutput(toolCall.output);
    return output?.feature === 'holland_assessment' && output?.top_code;
  });

  if (!hasSuccessfulHollandResult) return toolCalls;

  return toolCalls.filter((toolCall) => {
    const output = normalizeToolOutput(toolCall.output);
    const isSupersededHollandError = output?.feature === 'holland_assessment'
      && (output?.status === 'error' || output?.error)
      && !output?.questions
      && !output?.top_code;
    return !isSupersededHollandError;
  });
}

const riasecLabels = {
  R: 'Realistic - Thực tế',
  I: 'Investigative - Nghiên cứu',
  A: 'Artistic - Nghệ thuật',
  S: 'Social - Xã hội',
  E: 'Enterprising - Dẫn dắt',
  C: 'Conventional - Quy củ'
};

function HollandResultCard({ result }) {
  const scores = result?.scores || {};
  const topCode = result?.top_code || 'Đang cập nhật';
  const answeredCount = result?.answered_count;
  const hasScores = Object.keys(scores).length > 0;

  return (
    <div className="holland-result-card">
      <div className="holland-result-header">
        <div>
          <div className="holland-eyebrow">Kết quả Holland Test</div>
          <h3>{topCode}</h3>
          <p>{result?.interpretation_vi || 'Agent đã ghi nhận kết quả bài test của bạn.'}</p>
        </div>
        {answeredCount && (
          <div className="holland-result-count">
            <strong>{answeredCount}</strong>
            <span>câu đã trả lời</span>
          </div>
        )}
      </div>

      {hasScores && (
        <div className="holland-score-list" aria-label="Điểm RIASEC">
          {Object.entries(riasecLabels).map(([code, label]) => {
            const score = Number(scores[code] || 0);
            const percent = Math.round(score * 100);
            return (
              <div className="holland-score-row" key={code}>
                <div className="holland-score-meta">
                  <span>{code}</span>
                  <strong>{label}</strong>
                  <em>{percent}%</em>
                </div>
                <div className="holland-score-track">
                  <div className="holland-score-fill" style={{ width: `${percent}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ProfileScanResultCard({ result }) {
  const grade = result?.grade || 'E';
  const dimensions = Array.isArray(result?.score_dimensions) ? result.score_dimensions : [];
  const skills = Array.isArray(result?.extracted_skills) ? result.extracted_skills : [];
  const recommendations = Array.isArray(result?.recommendations) ? result.recommendations : [];
  const strengths = Array.isArray(result?.strengths) ? result.strengths : [];

  return (
    <div className="profile-scan-card">
      <div className="profile-scan-header">
        <div className={`profile-rank-mark rank-${grade.toLowerCase()}`}>
          <span>{grade}</span>
        </div>
        <div className="profile-scan-title">
          <div className="profile-scan-eyebrow">CV Benchmark</div>
          <h3>{result?.target_role || 'Profile Scanner'}</h3>
          <p>{result?.message_vi || 'Profile Scanner đã hoàn tất phân tích CV.'}</p>
          <div className="profile-analysis-mode">
            {result?.ai_extraction_used ? (
              <span>Gemini-assisted extraction · confidence {Math.round(Number(result?.ai_extraction_confidence || 0) * 100)}%</span>
            ) : (
              <span>Heuristic fallback analysis</span>
            )}
          </div>
        </div>
        <div className="profile-total-score">
          <strong>{Math.round(Number(result?.total_score || 0))}</strong>
          <span>/100</span>
        </div>
      </div>

      {dimensions.length > 0 && (
        <div className="profile-dimension-list">
          {dimensions.map((dimension) => {
            const score = Math.round(Number(dimension.score || 0));
            return (
              <div className="profile-dimension-row" key={dimension.key || dimension.label}>
                <div className="profile-dimension-meta">
                  <strong>{dimension.label}</strong>
                  <span>{score}/100 · {Math.round(Number(dimension.weight || 0) * 100)}%</span>
                </div>
                <div className="profile-dimension-track">
                  <div className="profile-dimension-fill" style={{ width: `${score}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="profile-scan-grid">
        <div>
          <span className="profile-scan-section-title">Kỹ năng phát hiện</span>
          <div className="profile-skill-cloud">
            {skills.slice(0, 12).map((skill) => <span key={skill}>{skill}</span>)}
            {!skills.length && <em>Chưa phát hiện kỹ năng rõ ràng.</em>}
          </div>
        </div>
        <div>
          <span className="profile-scan-section-title">Gợi ý cải thiện</span>
          <ul className="profile-recommendations">
            {recommendations.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
            {!recommendations.length && strengths.slice(0, 3).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      </div>
    </div>
  );
}

function ToolResultSummary({ output }) {
  const normalizedOutput = normalizeToolOutput(output);
  const hasError = normalizedOutput?.status === 'error' || Boolean(normalizedOutput?.error);
  const errorMeta = [
    normalizedOutput?.method,
    normalizedOutput?.endpoint,
    normalizedOutput?.status_code ? `HTTP ${normalizedOutput.status_code}` : null
  ].filter(Boolean).join(' · ');
  const errorText = normalizedOutput?.message
    || normalizedOutput?.detail
    || normalizedOutput?.error
    || 'Agent gặp lỗi khi xử lý yêu cầu.';
  const text = normalizedOutput?.response
    || normalizedOutput?.summary
    || normalizedOutput?.message
    || normalizedOutput?.message_vi
    || normalizedOutput?.content
    || (typeof output === 'string' ? output : 'Agent đã hoàn tất bước xử lý.');

  if (hasError) {
    return (
      <div className="tool-summary-card error">
        <AlertCircle size={16} />
        <span>
          <strong>Không thể hoàn tất bước xử lý.</strong>
          {errorMeta && <small>{errorMeta}</small>}
          <em>{errorText}</em>
        </span>
      </div>
    );
  }

  return (
    <div className="tool-summary-card">
      <CheckCircle2 size={16} />
      <span>{text}</span>
    </div>
  );
}

function HollandTestForm({ output, onSendMessage }) {
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const questions = output?.questions || [];
  const latestResult = output?.latest_result;
  const answeredCount = Object.keys(answers).length;
  const isComplete = answeredCount === questions.length;

  if (!questions.length) return null;

  const handleSubmit = async () => {
    if (!isComplete || submitted || submitting) return;
    const payload = questions.map((question) => ({
      question_id: question.id,
      score: answers[question.id]
    }));
    const displayText = `Mình đã hoàn thành Holland Test với ${questions.length} câu trả lời. Hãy chấm điểm và lưu kết quả RIASEC vào hồ sơ của mình.`;
    const backendText = [
      'Mình đã hoàn thành Holland Test. Hãy chấm điểm bằng profile_scanner tool với task="holland_score" và answers_json sau:',
      '```json',
      JSON.stringify(payload, null, 2),
      '```'
    ].join('\n');
    setSubmitting(true);
    setSubmitError('');
    const ok = await onSendMessage({
      displayText,
      backendText
    });
    setSubmitting(false);
    if (ok) {
      setSubmitted(true);
    } else {
      setSubmitError('Chưa gửi được câu trả lời. Vui lòng thử lại sau khi agent hoàn tất hoặc kiểm tra kết nối backend.');
    }
  };

  return (
    <div className="holland-form">
      <div className="holland-form-header">
        <div>
          <div className="holland-eyebrow">Bài đánh giá RIASEC</div>
          <h3>Holland Test</h3>
          <p>Chọn mức độ giống bạn từ 1 đến 5. Kết quả sẽ được agent chấm điểm và lưu vào hồ sơ định hướng nghề nghiệp.</p>
        </div>
        <div className="holland-progress">
          <strong>{answeredCount}/{questions.length}</strong>
          <span>đã trả lời</span>
        </div>
      </div>

      {latestResult && (
        <div className="holland-latest">
          <span>Kết quả gần nhất</span>
          <strong>{latestResult.top_code}</strong>
          <small>{latestResult.interpretation_vi}</small>
        </div>
      )}

      <div className="holland-scale">
        <span>1 - Rất không giống</span>
        <span>3 - Trung lập</span>
        <span>5 - Rất giống</span>
      </div>

      <div className="holland-question-list">
        {questions.map((question, index) => (
          <div className="holland-question" key={question.id}>
            <div className="holland-question-copy">
              <span>{question.id}</span>
              <p>{index + 1}. {question.text_vi}</p>
            </div>
            <div className="holland-rating" role="radiogroup" aria-label={question.text_vi}>
              {[1, 2, 3, 4, 5].map((score) => (
                <button
                  key={score}
                  className={answers[question.id] === score ? 'selected' : ''}
                  onClick={() => setAnswers((prev) => ({ ...prev, [question.id]: score }))}
                  type="button"
                  aria-pressed={answers[question.id] === score}
                >
                  {score}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="holland-form-footer">
        <span>{isComplete ? 'Sẵn sàng chấm điểm.' : `Còn ${questions.length - answeredCount} câu chưa trả lời.`}</span>
        <button onClick={handleSubmit} disabled={!isComplete || submitted || submitting} type="button">
          {submitted ? 'Đã gửi' : submitting ? 'Đang gửi...' : 'Gửi câu trả lời'}
        </button>
      </div>
      {submitError && <div className="holland-form-error">{submitError}</div>}
    </div>
  );
}

function AcademicArchitectInputConfirmWidget({ output, onSendMessage }) {
  const normalized = normalizeToolOutput(output) || {};
  const careerGoal = normalized.career_goal || '';
  const skills = normalized.current_skills || [];
  const [newSkill, setNewSkill] = useState('');

  const handleAddSkill = () => {
    if (!newSkill.trim()) return;
    onSendMessage(`thêm kỹ năng ${newSkill.trim()}`);
    setNewSkill('');
  };

  const handleRemoveSkill = (skill) => {
    onSendMessage(`xóa kỹ năng ${skill}`);
  };

  const handleConfirm = () => {
    onSendMessage("Xác nhận và dựng lộ trình học tập");
  };

  return (
    <div className="academic-confirm-widget">
      <div className="confirm-widget-header">
        <h4>Xác nhận thông tin lộ trình học tập</h4>
        <p>Vui lòng kiểm tra mục tiêu nghề nghiệp và các kỹ năng của bạn trước khi chúng tôi tạo lộ trình.</p>
      </div>
      
      <div className="confirm-field">
        <span className="field-label">Mục tiêu nghề nghiệp:</span>
        <strong className="field-value">{careerGoal || 'Chưa xác định'}</strong>
      </div>
      
      <div className="confirm-field">
        <span className="field-label">Kỹ năng hiện tại của bạn:</span>
        <div className="confirm-skills-list">
          {skills.map((skill) => (
            <span key={skill} className="skill-confirm-tag">
              {skill}
              <button 
                type="button" 
                className="skill-remove-btn" 
                onClick={() => handleRemoveSkill(skill)}
                title="Xóa kỹ năng này"
              >
                ×
              </button>
            </span>
          ))}
          {skills.length === 0 && <em style={{ fontSize: '0.85em', color: 'var(--text-muted)' }}>Chưa có kỹ năng nào. Bạn có thể thêm ở dưới.</em>}
        </div>
      </div>
      
      <div className="confirm-actions-bar">
        <div className="add-skill-inline">
          <input 
            type="text" 
            placeholder="Thêm kỹ năng mới..." 
            value={newSkill} 
            onChange={(e) => setNewSkill(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleAddSkill();
              }
            }}
          />
          <button type="button" onClick={handleAddSkill}>Thêm</button>
        </div>
        <button type="button" className="confirm-generate-btn" onClick={handleConfirm}>
          Xác nhận & Dựng lộ trình
        </button>
      </div>
    </div>
  );
}

function CalendarSyncWidget({ output, user, backendUrl }) {
  const courses = output.courses || [];
  const lackingSkills = output.lacking_skills || [];
  const careerGoal = output.career_goal || 'Lộ trình học tập';

  const [calendarStatus, setCalendarStatus] = useState('idle'); // 'idle' | 'loading' | 'success' | 'error'
  const [calendarMessage, setCalendarMessage] = useState('');

  const handleAddToCalendar = async () => {
    if (!user || calendarStatus === 'loading') return;
    if (courses.length === 0) return;
    
    const courseToSchedule = courses[0];

    setCalendarStatus('loading');
    try {
      const res = await fetch(`${backendUrl}/calendar/append`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user.google_id
        },
        body: JSON.stringify({
          career_goal: careerGoal,
          lacking_skills: lackingSkills,
          courses: [{ 
            name: courseToSchedule.name, 
            url: courseToSchedule.url,
            duration: courseToSchedule.duration || '15 giờ',
            workload: courseToSchedule.workload || ''
          }]
        })
      });
      if (!res.ok) throw new Error('Không thể đồng bộ lịch học');
      const data = await res.json();
      setCalendarStatus('success');
      setCalendarMessage(data.message || 'Đã đồng bộ thành công!');
    } catch (err) {
      console.error(err);
      setCalendarStatus('error');
      setCalendarMessage('Đồng bộ lịch thất bại. Vui lòng thử lại sau.');
    }
  };

  return (
    <div className="calendar-sync-card">
      <div className="calendar-card-header">
        <span className="calendar-card-icon" role="img" aria-label="calendar">📅</span>
        <h4>Lập kế hoạch học tập trên Google Calendar</h4>
      </div>
      <p className="calendar-card-desc">
        Đồng bộ lộ trình này để tự động tạo lịch học nhắc nhở cho khóa học này trên Google Calendar.
      </p>
      <div className="calendar-card-actions">
        {calendarStatus === 'idle' && (
          <button className="calendar-sync-btn" onClick={handleAddToCalendar} disabled={courses.length === 0}>
            Đồng bộ khóa học vào Google Calendar
          </button>
        )}
        {calendarStatus === 'loading' && (
          <button className="calendar-sync-btn loading" disabled>
            <span className="btn-spinner" />
            Đang đồng bộ...
          </button>
        )}
        {calendarStatus === 'success' && (
          <div className="calendar-sync-success-msg">
            <span className="success-check">✓</span>
            <span>{calendarMessage}</span>
          </div>
        )}
        {calendarStatus === 'error' && (
          <div className="calendar-sync-error-msg">
            <span className="error-cross">✕</span>
            <span>{calendarMessage}</span>
            <button className="calendar-retry-btn" onClick={handleAddToCalendar}>
              Thử lại
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ToolCallWidget({ toolName, output, status, onSendMessage, user, backendUrl }) {
  const [expanded, setExpanded] = useState(true);
  const info = agentInfo[toolName] || {
    label: toolName,
    icon: Terminal,
    themeClass: 'default'
  };
  const Icon = info.icon;
  const normalizedOutput = normalizeToolOutput(output);
  const isHollandOutput = normalizedOutput?.feature === 'holland_assessment';
  const isProfileScanOutput = normalizedOutput?.feature === 'profile_scan';
  const shouldRenderHollandForm = isHollandOutput
    && normalizedOutput?.questions
    && status === 'completed';
  const shouldRenderHollandResult = isHollandOutput
    && normalizedOutput?.top_code
    && status === 'completed';
  const shouldRenderProfileScanResult = isProfileScanOutput
    && normalizedOutput?.grade
    && status === 'completed';
  const shouldRenderVerifier = toolName === 'academic_architect_input_verifier'
    && status === 'completed';
  const toolLabel = isHollandOutput && toolName === 'profile_scanner'
    ? `${info.label} · Holland Test`
    : info.label;

  return (
    <div className={`tool-call-widget ${info.themeClass}`}>
      <button className="tool-call-header" onClick={() => setExpanded(!expanded)} type="button">
        <div className="tool-title">
          <Icon size={16} />
          <span>{toolLabel}</span>
        </div>
        <div className="tool-status">
          {status === 'running' && (
            <div className="tool-status running">
              <div className="spinner" />
              <span>Đang chạy</span>
            </div>
          )}
          {status === 'completed' && (
            <div className="tool-status completed">
              <CheckCircle2 size={14} />
              <span>Hoàn tất</span>
            </div>
          )}
          {status === 'error' && (
            <div className="tool-status error">
              <AlertCircle size={14} />
              <span>Lỗi</span>
            </div>
          )}
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {expanded && (
        <div className="tool-content">
          {output && (
            <div className="tool-section">
              {shouldRenderHollandForm ? (
                <HollandTestForm output={normalizedOutput} onSendMessage={onSendMessage} />
              ) : shouldRenderHollandResult ? (
                <HollandResultCard result={normalizedOutput} />
              ) : shouldRenderProfileScanResult ? (
                <ProfileScanResultCard result={normalizedOutput} />
              ) : shouldRenderVerifier ? (
                <AcademicArchitectInputConfirmWidget output={normalizedOutput} onSendMessage={onSendMessage} />
              ) : (
                <ToolResultSummary output={output} />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AgentModule({ agentKey, active }) {
  const info = agentInfo[agentKey];
  const Icon = info.icon;

  return (
    <div className={`agent-module ${info.themeClass} ${active ? 'active' : ''}`}>
      <div className="agent-module-icon">
        <Icon size={18} />
      </div>
      <div>
        <div className="agent-module-title">{info.label}</div>
        <div className="agent-module-desc">{info.description}</div>
      </div>
      <div className="agent-module-state">{active ? 'Đang chạy' : 'Sẵn sàng'}</div>
    </div>
  );
}

function CvAttachmentChip({ attachment, onRemove, compact = false }) {
  if (!attachment) return null;

  return (
    <div className={`cv-attachment-chip ${compact ? 'compact' : ''}`}>
      <div className="cv-attachment-icon">
        <FileText size={16} />
      </div>
      <div className="cv-attachment-copy">
        <strong>{attachment.name}</strong>
        <span>
          {attachment.label} · {formatFileSize(attachment.size)}
          {attachment.statusLabel ? ` · ${attachment.statusLabel}` : ''}
        </span>
      </div>
      {onRemove && (
        <button className="cv-attachment-remove" onClick={onRemove} type="button" title="Gỡ CV đính kèm">
          <X size={14} />
        </button>
      )}
    </div>
  );
}

function LoginScreen({ googleClientId }) {
  return (
    <div className="login-screen">
      <div className="login-shell">
        <section className="login-hero">
          <div className="brand-mark">
            <Sparkles size={22} />
            <span>Z-MentorAI</span>
          </div>
          <h1>Không gian AI giúp bạn ra quyết định nghề nghiệp.</h1>
          <p>
            Đưa CV, mục tiêu và câu hỏi của bạn vào một nơi. Z-MentorAI giữ cuộc trò chuyện tập trung vào quét hồ sơ,
            phân tích thị trường và lộ trình học tập.
          </p>
          <div className="login-proof-grid">
            <div>
              <strong>Hồ sơ</strong>
              <span>Đọc điểm mạnh và tín hiệu còn thiếu</span>
            </div>
            <div>
              <strong>Thị trường</strong>
              <span>So sánh vai trò và kỳ vọng tuyển dụng</span>
            </div>
            <div>
              <strong>Lộ trình</strong>
              <span>Biến khoảng trống thành hướng học rõ ràng</span>
            </div>
          </div>
        </section>

        <section className="login-visual-panel">
          <div className="login-card">
            <h2>Bắt đầu phiên tư vấn</h2>
            <p>
              Đăng nhập bằng Google để tiếp tục các cuộc trò chuyện và lưu ngữ cảnh nghề nghiệp của bạn.
            </p>
            <div className="login-actions">
              <div id="google-signin-button" className="google-btn-container"></div>
              {!googleClientId && (
                <div className="login-config-note">Đang chờ cấu hình đăng nhập Google.</div>
              )}
            </div>
          </div>
          <LoginChatTerminal />
        </section>
      </div>
    </div>
  );
}

function AppHeader({ activeAgents, avatarSrc, user, onAvatarClick, onLogout }) {
  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo">
          <Sparkles size={20} />
        </div>
        <div>
          <h1 className="brand-title">Z-MentorAI</h1>
          <div className="brand-subtitle">Cố vấn nghề nghiệp</div>
        </div>
      </div>

      <div className="agent-status-bar">
        {Object.keys(agentInfo).map((agentKey) => (
          <div
            key={agentKey}
            className={`agent-badge ${agentInfo[agentKey].themeClass} ${activeAgents.includes(agentKey) ? 'active' : ''}`}
          >
            <div className="badge-dot" />
            <span>{agentInfo[agentKey].label}</span>
          </div>
        ))}
      </div>

      <div className="user-profile-section">
        <button className="avatar-wrapper" onClick={onAvatarClick} title="Tải ảnh đại diện" type="button">
          {avatarSrc ? (
            <img src={avatarSrc} alt="Ảnh đại diện người dùng" className="user-avatar" />
          ) : (
            <div className="user-avatar-placeholder">
              <User size={18} />
            </div>
          )}
          <div className="avatar-hover-overlay">
            <Upload size={14} />
          </div>
        </button>
        <div className="user-info">
          <div className="user-name">{user.name}</div>
          <div className="user-email">{user.email}</div>
        </div>
        <button className="logout-btn" onClick={onLogout} title="Đăng xuất" type="button">
          <LogOut size={16} />
        </button>
      </div>
    </header>
  );
}

function SessionSidebar({ sessions, activeSessionId, isLoading, onCreateNewSession, onSelectSession, onDeleteSession }) {
  return (
    <aside className="sidebar">
      <button className="new-chat-btn" onClick={onCreateNewSession} disabled={isLoading} type="button">
        <Plus size={16} />
        <span>Cuộc trò chuyện mới</span>
      </button>

      <div className="sidebar-intel-card">
        <div className="sidebar-intel-icon">
          <Network size={16} />
        </div>
        <div>
          <strong>Các agent nghề nghiệp</strong>
          <span>Hồ sơ, thị trường và lộ trình học sẽ đi cùng cuộc trò chuyện này.</span>
        </div>
      </div>

      <div className="sessions-list">
        <div className="sidebar-section-title">
          <MessageSquare size={12} />
          <span>Gần đây</span>
        </div>
        {sessions.map((session) => (
          <button
            key={session.id}
            className={`session-item ${activeSessionId === session.id ? 'active' : ''}`}
            onClick={() => onSelectSession(session.id)}
            type="button"
          >
            <span className="session-item-title">{session.title}</span>
            <span
              className="delete-session-btn"
              onClick={(event) => onDeleteSession(session.id, event)}
              role="button"
              tabIndex={0}
              title="Xóa cuộc trò chuyện"
            >
              <Trash2 size={13} />
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}

function WelcomeState({ user, activeAgents, onSendMessage }) {
  return (
    <div className="welcome-container">
      <div className="welcome-copy">
        <h2>Hôm nay mình sẽ cùng phân tích bước đi nghề nghiệp nào, {user.name.split(' ')[0]}?</h2>
        <p>
          Hãy đặt câu hỏi trực tiếp, đính kèm CV hoặc bắt đầu bằng một gợi ý bên dưới.
        </p>
      </div>

      <div className="agent-module-grid">
        {Object.keys(agentInfo).map((agentKey) => (
          <AgentModule key={agentKey} agentKey={agentKey} active={activeAgents.includes(agentKey)} />
        ))}
      </div>

      <div className="suggested-questions">
        {suggestedQuestions.map((question) => {
          const info = agentInfo[question.agent];
          const Icon = info.icon;
          return (
            <button
              key={question.title}
              className={`suggested-card ${info.themeClass}`}
              onClick={() => onSendMessage(question.prompt)}
              type="button"
            >
              <span className="suggested-icon">
                <Icon size={16} />
              </span>
              <span>
                <strong>{question.title}</strong>
                <small>{question.desc}</small>
              </span>
              <ArrowRight size={15} />
            </button>
          );
        })}
      </div>
    </div>
  );
}

function MessagesFeed({ messages, isLoading, activeAgents, messagesEndRef, onSendMessage, user, backendUrl }) {
  return (
    <div className="messages-feed">
      {messages.map((msg) => {
        const visibleToolCalls = getVisibleToolCalls(msg.toolCalls || []);
        const hideAssistantContent = msg.role === 'assistant'
          && hasHollandInteractiveToolCall(visibleToolCalls);

        return (
          <div key={msg.id} className={`message-wrapper ${msg.role}`}>
            <div className="message-header">{msg.role === 'user' ? 'Bạn' : 'Điều phối viên'}</div>

            {msg.role === 'assistant' && visibleToolCalls.filter(toolCall => toolCall.name !== 'academic_architect').map((toolCall) => (
              <ToolCallWidget
                key={toolCall.id}
                toolName={toolCall.name}
                input={toolCall.input}
                output={toolCall.output}
                status={toolCall.status}
                onSendMessage={onSendMessage}
                user={user}
                backendUrl={backendUrl}
              />
            ))}

            {!hideAssistantContent && (msg.content || msg.role === 'user') && (
              <div className="message-bubble">
                {msg.role === 'user' ? (
                  <>
                    {msg.attachment && <CvAttachmentChip attachment={msg.attachment} compact />}
                    <p>{msg.content}</p>
                  </>
                ) : (
                  <>
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                    {(() => {
                      const academicToolCall = msg.toolCalls?.find(
                        (t) => t.name === 'academic_architect' && t.status === 'completed'
                      );
                      if (!academicToolCall) return null;
                      const output = normalizeToolOutput(academicToolCall.output);
                      if (!output) return null;
                      return (
                        <div className="orches-calendar-sync-wrapper" style={{ marginTop: '1rem' }}>
                          <CalendarSyncWidget output={output} user={user} backendUrl={backendUrl} />
                        </div>
                      );
                    })()}
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}

      {isLoading && activeAgents.length === 0 && (
        <div className="thinking-wrapper">
          <span>Đang tổng hợp phản hồi</span>
          <div className="thinking-dots">
            <div className="thinking-dot" />
            <div className="thinking-dot" />
            <div className="thinking-dot" />
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
}

function ChatInput({
  inputValue,
  setInputValue,
  onSendMessage,
  handleKeyDown,
  isLoading,
  activeSessionId,
  textareaRef,
  cvAttachment,
  cvInputRef,
  onCvAttachClick,
  onCvFileChange,
  onRemoveCvAttachment,
  cvUploadError
}) {
  return (
    <div className="input-panel">
      <CvAttachmentChip attachment={cvAttachment} onRemove={onRemoveCvAttachment} />
      {cvUploadError && <div className="holland-form-error">{cvUploadError}</div>}
      <div className="input-container">
        <button
          className="attach-cv-button"
          onClick={onCvAttachClick}
          disabled={isLoading}
          type="button"
          title="Đính kèm CV"
        >
          <Paperclip size={17} />
        </button>
        <textarea
          ref={textareaRef}
          className="chat-input"
          placeholder="Hỏi Z-MentorAI hoặc đính kèm CV..."
          rows={1}
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading || !activeSessionId}
        />
        <button
          className="send-button"
          onClick={() => onSendMessage()}
          disabled={isLoading || (!inputValue.trim() && !cvAttachment) || !activeSessionId}
          type="button"
        >
          <Send size={16} />
        </button>
      </div>
      <input
        ref={cvInputRef}
        className="cv-file-input"
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={onCvFileChange}
      />
    </div>
  );
}

function ChatWorkspace({
  user,
  messages,
  isLoading,
  activeAgents,
  messagesEndRef,
  onSendMessage,
  inputValue,
  setInputValue,
  handleKeyDown,
  activeSessionId,
  textareaRef,
  cvAttachment,
  cvInputRef,
  onCvAttachClick,
  onCvFileChange,
  onRemoveCvAttachment,
  cvUploadError,
  backendUrl
}) {
  return (
    <div className="chat-area">
      {messages.length === 0 ? (
        <WelcomeState user={user} activeAgents={activeAgents} onSendMessage={onSendMessage} />
      ) : (
        <MessagesFeed
          messages={messages}
          isLoading={isLoading}
          activeAgents={activeAgents}
          messagesEndRef={messagesEndRef}
          onSendMessage={onSendMessage}
          user={user}
          backendUrl={backendUrl}
        />
      )}

      <ChatInput
        inputValue={inputValue}
        setInputValue={setInputValue}
        onSendMessage={onSendMessage}
        handleKeyDown={handleKeyDown}
        isLoading={isLoading}
        activeSessionId={activeSessionId}
        textareaRef={textareaRef}
        cvAttachment={cvAttachment}
        cvInputRef={cvInputRef}
        onCvAttachClick={onCvAttachClick}
        onCvFileChange={onCvFileChange}
        onRemoveCvAttachment={onRemoveCvAttachment}
        cvUploadError={cvUploadError}
      />
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('z_mentor_user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [, setAuthLoading] = useState(false);
  const [googleClientId, setGoogleClientId] = useState(null);
  const [activeAgents, setActiveAgents] = useState([]);
  const [cvAttachment, setCvAttachment] = useState(null);
  const [cvUploadError, setCvUploadError] = useState('');

  const backendUrl = useMemo(() => import.meta.env.VITE_API_URL || window.location.origin, []);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const avatarInputRef = useRef(null);
  const cvInputRef = useRef(null);
  const bootstrappedSessionsRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [inputValue]);

  const handleCreateNewSession = useCallback(async () => {
    if (isLoading || !user) return null;
    try {
      const res = await fetch(`${backendUrl}/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user.google_id
        },
        body: JSON.stringify({ title: 'Cuộc trò chuyện mới' })
      });
      if (!res.ok) throw new Error('Không thể tạo cuộc trò chuyện mới');
      const newSession = await res.json();
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      localStorage.setItem(`z_mentor_active_session_${user.google_id}`, newSession.id);
      setMessages([]);
      setCvAttachment(null);
      return newSession.id;
    } catch (err) {
      console.error(err);
      alert('Không thể khởi tạo cuộc trò chuyện mới.');
      return null;
    }
  }, [backendUrl, isLoading, user]);

  const handleSelectSession = useCallback(async (sessionId) => {
    if (isLoading || !user) return;
    try {
      const res = await fetch(`${backendUrl}/sessions/${sessionId}`, {
        headers: { 'X-User-Id': user.google_id }
      });
      if (!res.ok) throw new Error('Không thể tải chi tiết cuộc trò chuyện');
      const session = await res.json();

      setActiveSessionId(sessionId);
      localStorage.setItem(`z_mentor_active_session_${user.google_id}`, sessionId);
      setCvAttachment(null);

      const uiMessages = session.messages.map((message, idx) => ({
        id: `msg-${idx}-${Date.now()}`,
        role: message.role,
        content: message.content,
        attachment: message.attachment,
        toolCalls: normalizeStoredToolCalls(message.tool_calls || message.toolCalls)
      }));
      setMessages(uiMessages);
    } catch (err) {
      console.error(err);
      alert('Không thể tải lịch sử trò chuyện.');
    }
  }, [backendUrl, isLoading, user]);

  const fetchSessions = useCallback(async (keepActiveSession = false) => {
    if (!user) return;
    try {
      const res = await fetch(`${backendUrl}/sessions`, {
        headers: { 'X-User-Id': user.google_id }
      });
      if (!res.ok) throw new Error('Không thể tải danh sách cuộc trò chuyện');
      const data = await res.json();
      setSessions(data);

      if (data.length > 0) {
        if (keepActiveSession && activeSessionId) return;
        const lastSessionId = localStorage.getItem(`z_mentor_active_session_${user.google_id}`) || data[0].id;
        const exists = data.some((session) => session.id === lastSessionId);
        const targetSessionId = exists ? lastSessionId : data[0].id;
        await handleSelectSession(targetSessionId);
      } else {
        await handleCreateNewSession();
      }
    } catch (err) {
      console.error(err);
    }
  }, [activeSessionId, backendUrl, handleCreateNewSession, handleSelectSession, user]);

  const handleGoogleLoginResponse = useCallback(async (response) => {
    setAuthLoading(true);
    try {
      const res = await fetch(`${backendUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: response.credential })
      });
      if (!res.ok) throw new Error('Xác thực Google thất bại');
      const userData = await res.json();
      localStorage.setItem('z_mentor_user', JSON.stringify(userData));
      setUser(userData);
    } catch (err) {
      console.error(err);
      alert('Đăng nhập thất bại. Vui lòng kiểm tra kết nối tới Orchestrator.');
    } finally {
      setAuthLoading(false);
    }
  }, [backendUrl]);

  useEffect(() => {
    if (!user) {
      fetch(`${backendUrl}/auth/config`)
        .then((res) => res.json())
        .then((data) => {
          if (data.google_client_id) setGoogleClientId(data.google_client_id);
        })
        .catch((err) => console.error('Không thể tải cấu hình Google Client ID', err));
    }
  }, [backendUrl, user]);

  useEffect(() => {
    if (!user && googleClientId && window.google?.accounts?.id) {
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: handleGoogleLoginResponse
      });

      const btnParent = document.getElementById('google-signin-button');
      if (btnParent) {
        window.google.accounts.id.renderButton(btnParent, {
          theme: 'outline',
          size: 'large',
          width: 320
        });
      }
    }
  }, [googleClientId, handleGoogleLoginResponse, user]);

  useEffect(() => {
    if (!user) {
      bootstrappedSessionsRef.current = null;
      return;
    }

    const bootstrapKey = `${backendUrl}:${user.google_id}`;
    if (bootstrappedSessionsRef.current === bootstrapKey) return;

    bootstrappedSessionsRef.current = bootstrapKey;
    fetchSessions();
  }, [backendUrl, fetchSessions, user]);

  const handleDeleteSession = async (sessionId, event) => {
    event.stopPropagation();
    if (isLoading || !user) return;
    if (!window.confirm('Bạn có chắc muốn xóa cuộc trò chuyện này không?')) return;

    try {
      const res = await fetch(`${backendUrl}/sessions/${sessionId}`, {
        method: 'DELETE',
        headers: { 'X-User-Id': user.google_id }
      });
      if (!res.ok) throw new Error('Không thể xóa cuộc trò chuyện');

      const updatedSessions = sessions.filter((session) => session.id !== sessionId);
      setSessions(updatedSessions);

      if (activeSessionId === sessionId) {
        if (updatedSessions.length > 0) {
          handleSelectSession(updatedSessions[0].id);
        } else {
          handleCreateNewSession();
        }
      }
    } catch (err) {
      console.error(err);
      alert('Không thể xóa cuộc trò chuyện.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('z_mentor_user');
    localStorage.removeItem(`z_mentor_active_session_${user?.google_id}`);
    setUser(null);
    setSessions([]);
    setActiveSessionId(null);
    setMessages([]);
    setCvAttachment(null);
  };

  const handleAvatarClick = () => {
    avatarInputRef.current?.click();
  };

  const handleCvAttachClick = async () => {
    setCvUploadError('');
    if (!activeSessionId) {
      const sessionId = await handleCreateNewSession();
      if (!sessionId) {
        setCvUploadError('Không thể tạo phiên chat để đính kèm CV. Vui lòng kiểm tra kết nối backend.');
        return;
      }
    }
    cvInputRef.current?.click();
  };

  const handleRemoveCvAttachment = () => {
    setCvAttachment(null);
    setCvUploadError('');
    if (cvInputRef.current) cvInputRef.current.value = '';
  };

  const handleCvFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setCvUploadError('');

    const extension = getFileExtension(file.name);
    const isAcceptedType = acceptedCvMimeTypes.has(file.type) || acceptedCvExtensions.includes(extension);

    if (!isAcceptedType) {
      alert('Vui lòng tải CV ở định dạng PDF hoặc DOCX.');
      event.target.value = '';
      return;
    }

    if (file.size > maxCvFileSizeBytes) {
      alert(`File CV quá lớn. Vui lòng giữ dung lượng dưới ${formatFileSize(maxCvFileSizeBytes)}.`);
      event.target.value = '';
      return;
    }

    setCvAttachment({
      file,
      name: file.name,
      size: file.size,
      type: file.type || 'application/octet-stream',
      extension,
      label: extension ? extension.toUpperCase() : 'CV'
    });
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file || !user) return;

    if (!file.type.startsWith('image/')) {
      alert('Vui lòng tải lên một file ảnh.');
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
        if (!res.ok) throw new Error('Tải ảnh thất bại');
        const updatedUser = await res.json();
        localStorage.setItem('z_mentor_user', JSON.stringify(updatedUser));
        setUser(updatedUser);
      } catch (err) {
        console.error(err);
        alert('Không thể lưu ảnh đại diện lên backend.');
      }
    };
    reader.readAsDataURL(file);
  };

  const uploadCvAttachment = useCallback(async (attachment, messageText) => {
    if (!attachment?.file || !user || !activeSessionId) return null;

    const formData = new FormData();
    formData.append('file', attachment.file);
    formData.append('session_id', activeSessionId);
    formData.append('message', messageText);

    const response = await fetch(`${backendUrl}/profile-scanner/cv/upload`, {
      method: 'POST',
      headers: {
        'X-User-Id': user.google_id
      },
      body: formData
    });

    if (!response.ok) {
      let detail = `Không thể tải CV lên, mã trạng thái ${response.status}.`;
      try {
        const payload = await response.json();
        detail = payload?.detail?.detail || payload?.detail || payload?.message || detail;
        if (typeof detail !== 'string') detail = JSON.stringify(detail);
      } catch {
        detail = await response.text();
      }
      throw new Error(detail);
    }

    return response.json();
  }, [activeSessionId, backendUrl, user]);

  const handleSendMessage = useCallback(async (textToSend) => {
    const structuredMessage = textToSend && typeof textToSend === 'object' ? textToSend : null;
    const query = String(structuredMessage?.displayText || (!structuredMessage ? textToSend : '') || inputValue).trim();
    const backendQuery = String(structuredMessage?.backendText || query).trim();
    const activeCvAttachment = cvAttachment;
    if ((!query && !activeCvAttachment) || isLoading || !activeSessionId || !user) return false;

    if (!textToSend) setInputValue('');

    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `assistant-${Date.now()}`;
    const messageText = query || 'Hãy quét CV này và tóm tắt độ phù hợp hồ sơ, các tín hiệu còn thiếu và bước tiếp theo nên làm.';
    let attachmentMeta = null;

    if (activeCvAttachment) {
      setIsLoading(true);
      setCvUploadError('');
      setCvAttachment((prev) => prev ? { ...prev, statusLabel: 'Đang tải CV lên...' } : prev);
      try {
        const uploadResult = await uploadCvAttachment(activeCvAttachment, messageText);
        attachmentMeta = {
          name: uploadResult.original_filename || activeCvAttachment.name,
          size: uploadResult.file_size_bytes || activeCvAttachment.size,
          type: uploadResult.mime_type || activeCvAttachment.type,
          extension: activeCvAttachment.extension,
          label: activeCvAttachment.label,
          cv_document_id: uploadResult.cv_document_id,
          statusLabel: 'Đã lưu CV'
        };
        setCvAttachment(null);
      } catch (err) {
        console.error('CV upload failed:', err);
        setCvUploadError(err.message || 'Không thể tải CV lên.');
        setCvAttachment((prev) => prev ? { ...prev, statusLabel: 'Không thể tải CV' } : prev);
        if (!textToSend) setInputValue(query);
        setIsLoading(false);
        return false;
      }
    }

    const backendMessage = attachmentMeta
      ? [
        messageText,
        '',
        `CV uploaded successfully with cv_document_id="${attachmentMeta.cv_document_id}".`,
        `File: ${attachmentMeta.name}, ${attachmentMeta.label}, ${formatFileSize(attachmentMeta.size)}.`,
        'Call profile_scanner with task="scan_profile" and pass this exact cv_document_id. Only use Profile Scanner output; do not invent CV analysis beyond extracted data.'
      ].join('\n')
      : backendQuery;

    setMessages((prev) => [
      ...prev,
      {
        id: userMessageId,
        role: 'user',
        content: messageText,
        attachment: attachmentMeta
      },
      {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        toolCalls: []
      }
    ]);
    setIsLoading(true);

    try {
      const response = await fetch(`${backendUrl}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user.google_id
        },
        body: JSON.stringify({
          message: backendMessage,
          session_id: activeSessionId,
          attachment: attachmentMeta
        })
      });

      if (!response.ok) throw new Error(`Lỗi HTTP, mã trạng thái: ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let rawStreamText = '';
      let streamError = '';
      const streamedToolCalls = new Map();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunkText = decoder.decode(value, { stream: true });
        rawStreamText += chunkText;
        buffer += chunkText;
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const dataStr = trimmed.slice(6);
          try {
            const data = JSON.parse(dataStr);

            if (data.type === 'tool_start') {
              streamedToolCalls.set(data.tool, {
                id: `${data.tool}-${Date.now()}`,
                name: data.tool,
                input: data.input,
                status: 'running'
              });
              setActiveAgents((prev) => [...new Set([...prev, data.tool])]);
              setMessages((prev) => prev.map((msg) => {
                if (msg.id !== assistantMessageId) return msg;
                const exists = msg.toolCalls.some((toolCall) => toolCall.name === data.tool);
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
              }));
            } else if (data.type === 'tool_end') {
              const previousToolCall = streamedToolCalls.get(data.tool);
              streamedToolCalls.set(data.tool, {
                id: previousToolCall?.id || `${data.tool}-${Date.now()}`,
                name: data.tool,
                input: previousToolCall?.input || data.input,
                output: data.output,
                status: 'completed'
              });
              setActiveAgents((prev) => prev.filter((tool) => tool !== data.tool));
              setMessages((prev) => prev.map((msg) => {
                if (msg.id !== assistantMessageId) return msg;
                const existingToolCall = msg.toolCalls.find((toolCall) => toolCall.name === data.tool);
                if (!existingToolCall) {
                  return {
                    ...msg,
                    toolCalls: [...msg.toolCalls, {
                      id: `${data.tool}-${Date.now()}`,
                      name: data.tool,
                      input: data.input,
                      output: data.output,
                      status: 'completed'
                    }]
                  };
                }
                return {
                  ...msg,
                  toolCalls: msg.toolCalls.map((toolCall) => (
                    toolCall.name === data.tool
                      ? { ...toolCall, output: data.output, status: 'completed' }
                      : toolCall
                  ))
                };
              }));
            } else if (data.type === 'token') {
              setMessages((prev) => prev.map((msg) => (
                msg.id === assistantMessageId
                  ? { ...msg, content: msg.content + data.content }
                  : msg
              )));
            } else if (data.type === 'error') {
              streamError = data.content || 'Agent gặp lỗi khi xử lý yêu cầu.';
              setMessages((prev) => prev.map((msg) => (
                msg.id === assistantMessageId
                  ? { ...msg, content: `${msg.content}\n\n*Lỗi agent: ${data.content}*` }
                  : msg
              )));
            }
          } catch (err) {
            console.error('Error parsing JSON chunk:', dataStr, err);
          }
        }
      }

      rawStreamText.split(/\r?\n/).forEach((line) => {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data: ')) return;
        try {
          const data = JSON.parse(trimmed.slice(6));
          if (data.type === 'tool_start' && !streamedToolCalls.has(data.tool)) {
            streamedToolCalls.set(data.tool, {
              id: `${data.tool}-${Date.now()}`,
              name: data.tool,
              input: data.input,
              status: 'running'
            });
          }
          if (data.type === 'tool_end') {
            const previousToolCall = streamedToolCalls.get(data.tool);
            streamedToolCalls.set(data.tool, {
              id: previousToolCall?.id || `${data.tool}-${Date.now()}`,
              name: data.tool,
              input: previousToolCall?.input || data.input,
              output: data.output,
              status: 'completed'
            });
          }
        } catch (err) {
          console.error('Error replaying stream event:', line, err);
        }
      });

      if (streamedToolCalls.size > 0) {
        const finalToolCalls = Array.from(streamedToolCalls.values());
        setMessages((prev) => prev.map((msg) => {
          if (msg.id !== assistantMessageId) return msg;
          const mergedToolCalls = [...msg.toolCalls];
          finalToolCalls.forEach((toolCall) => {
            const existingIndex = mergedToolCalls.findIndex((item) => item.name === toolCall.name);
            if (existingIndex >= 0) {
              mergedToolCalls[existingIndex] = { ...mergedToolCalls[existingIndex], ...toolCall };
            } else {
              mergedToolCalls.push(toolCall);
            }
          });
          return { ...msg, toolCalls: mergedToolCalls };
        }));
      }

      if (streamError) return false;

      await fetchSessions(true);
      return true;
    } catch (err) {
      console.error('Lỗi streaming:', err);
      setMessages((prev) => prev.map((msg) => {
        if (msg.id !== assistantMessageId) return msg;
        return {
          ...msg,
          content: msg.content
            ? `${msg.content}\n\n*Lỗi kết nối: ${err.message}*`
            : `Không thể kết nối tới Orchestrator tại ${backendUrl}. Hãy kiểm tra backend server và cấu hình CORS.`
        };
      }));
      return false;
    } finally {
      setIsLoading(false);
      setActiveAgents([]);
    }
  }, [activeSessionId, backendUrl, cvAttachment, fetchSessions, inputValue, isLoading, uploadCvAttachment, user]);

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  if (!user) {
    return (
      <LoginScreen
        googleClientId={googleClientId}
      />
    );
  }

  const avatarSrc = user.custom_avatar || user.picture;

  return (
    <div className="app-container">
        <AppHeader
          activeAgents={activeAgents}
          avatarSrc={avatarSrc}
          user={user}
          onAvatarClick={handleAvatarClick}
          onLogout={handleLogout}
        />

      <main className="chat-main">
        <SessionSidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          isLoading={isLoading}
          onCreateNewSession={handleCreateNewSession}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
        />

        <ChatWorkspace
          user={user}
          messages={messages}
          isLoading={isLoading}
          activeAgents={activeAgents}
          messagesEndRef={messagesEndRef}
          onSendMessage={handleSendMessage}
          inputValue={inputValue}
          setInputValue={setInputValue}
          handleKeyDown={handleKeyDown}
          activeSessionId={activeSessionId}
          textareaRef={textareaRef}
          cvAttachment={cvAttachment}
          cvInputRef={cvInputRef}
          onCvAttachClick={handleCvAttachClick}
          onCvFileChange={handleCvFileChange}
          onRemoveCvAttachment={handleRemoveCvAttachment}
          cvUploadError={cvUploadError}
          backendUrl={backendUrl}
        />
      </main>

      <input
        type="file"
        ref={avatarInputRef}
        onChange={handleFileChange}
        className="avatar-file-input"
        accept="image/*"
      />
    </div>
  );
}
