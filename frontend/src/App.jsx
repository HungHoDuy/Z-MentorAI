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
  Lock,
  Moon,
  MessageSquare,
  Network,
  Paperclip,
  Plus,
  Send,
  Sparkles,
  Settings,
  Sun,
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
const brandMarkSrc = '/assets/brand/z-mentorai-mark.png';

const uiText = {
  vi: {
    profile: 'Thông tin cá nhân', settings: 'Cài đặt', logout: 'Đăng xuất',
    personalTitle: 'Hồ sơ cá nhân', personalDesc: 'Thông tin dùng để các agent hiểu đúng bối cảnh nghề nghiệp của bạn.',
    fullName: 'Họ và tên', email: 'Email tài khoản', phone: 'Số điện thoại', location: 'Địa điểm',
    targetRole: 'Vị trí mục tiêu', linkedin: 'LinkedIn', github: 'GitHub', portfolio: 'Portfolio',
    save: 'Lưu thay đổi', saving: 'Đang lưu...', saved: 'Đã lưu thông tin.', currentCv: 'Hồ sơ CV hiện tại',
    noCv: 'Bạn chưa xác nhận CV nào làm hồ sơ hiện tại.', uploadDate: 'Ngày tải lên', version: 'Phiên bản hồ sơ',
    language: 'Ngôn ngữ', appearance: 'Giao diện', light: 'Sáng', dark: 'Tối', settingsDesc: 'Tùy chỉnh cách Z-MentorAI hiển thị trên thiết bị này.',
    backChat: 'Quay lại trò chuyện', assessmentResult: 'Kết quả bài đánh giá', answered: 'câu đã trả lời', learningTips: 'Gợi ý học tập'
  },
  en: {
    profile: 'Personal profile', settings: 'Settings', logout: 'Sign out',
    personalTitle: 'Personal profile', personalDesc: 'Information that helps agents understand your career context.',
    fullName: 'Full name', email: 'Account email', phone: 'Phone', location: 'Location',
    targetRole: 'Target role', linkedin: 'LinkedIn', github: 'GitHub', portfolio: 'Portfolio',
    save: 'Save changes', saving: 'Saving...', saved: 'Profile saved.', currentCv: 'Current CV profile',
    noCv: 'You have not confirmed a CV as your current profile.', uploadDate: 'Uploaded', version: 'Profile version',
    language: 'Language', appearance: 'Appearance', light: 'Light', dark: 'Dark', settingsDesc: 'Customize how Z-MentorAI appears on this device.',
    backChat: 'Back to chat', assessmentResult: 'Assessment result', answered: 'answered', learningTips: 'Learning suggestions'
  }
};

const scoreDimensionLabels = {
  vi: { role_skill_fit: 'Mức độ phù hợp kỹ năng', experience_evidence: 'Kinh nghiệm và bằng chứng', education_certification: 'Học vấn và chứng chỉ', career_readiness: 'Mức độ sẵn sàng nghề nghiệp', cv_clarity: 'Độ rõ ràng và khả năng đọc ATS' },
  en: { role_skill_fit: 'Role skill fit', experience_evidence: 'Experience and evidence', education_certification: 'Education and certification', career_readiness: 'Career-readiness signals', cv_clarity: 'CV clarity and ATS completeness' }
};

function getCvScoreCopy(grade, locale) {
  const normalizedGrade = String(grade || '').toUpperCase();
  const copy = {
    vi: {
      strong: 'Hồ sơ thể hiện mức độ sẵn sàng cao cho vị trí này. Hãy xem từng tiêu chí và duy trì các điểm mạnh nổi bật.',
      good: 'Hồ sơ có nền tảng phù hợp. Bạn có thể cải thiện thêm bằng cách làm rõ bằng chứng kỹ năng và tác động công việc.',
      developing: 'Hồ sơ đã có nền tảng ban đầu nhưng còn thiếu một số bằng chứng quan trọng cho vị trí này.',
      early: 'Hồ sơ chưa thể hiện đủ bằng chứng phù hợp. Hãy ưu tiên kỹ năng cốt lõi, dự án thực tế và kết quả đo lường được.',
      pending: 'Hệ thống đã đọc CV nhưng chưa có đủ dữ liệu để chấm điểm.'
    },
    en: {
      strong: 'Your CV shows strong readiness for this role. Review each category and continue building on the strongest evidence.',
      good: 'Your CV has a relevant foundation. Make your skill evidence and work impact more explicit to improve it further.',
      developing: 'Your CV has an initial foundation but still lacks important evidence for this role.',
      early: 'Your CV does not yet show enough relevant evidence. Prioritize core skills, practical projects, and measurable outcomes.',
      pending: 'The CV was processed, but there is not enough information to calculate a score.'
    }
  };
  const localeCopy = copy[locale] || copy.vi;
  if (['S', 'A'].includes(normalizedGrade)) return localeCopy.strong;
  if (normalizedGrade === 'B') return localeCopy.good;
  if (normalizedGrade === 'C') return localeCopy.developing;
  if (['D', 'E'].includes(normalizedGrade)) return localeCopy.early;
  return localeCopy.pending;
}

function localizeRecommendation(text, locale) {
  if (locale === 'en' || !text) return text;
  const dimensionEntries = Object.entries(scoreDimensionLabels.en);
  const matchedDimension = dimensionEntries.find(([, label]) => text.toLowerCase().includes(label.toLowerCase()));
  const label = matchedDimension ? scoreDimensionLabels.vi[matchedDimension[0]] : '';
  if (text.startsWith('Improve ') && label) return `Cải thiện ${label.toLowerCase()}: bổ sung bằng chứng cụ thể và có thể kiểm chứng trong CV.`;
  if (text.includes('No quantified achievement')) return 'Bổ sung thành tựu có số liệu hoặc tác động đo lường được.';
  if (text.includes('No email detected')) return 'Bổ sung email liên hệ rõ ràng trong CV.';
  return text;
}

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
  academic_architect_create_gantt: {
    label: 'Lộ Trình Học Tập',
    description: 'Biến khoảng trống kỹ năng thành lộ trình học tập thực tế.',
    icon: GraduationCap,
    themeClass: 'architect',
    accent: '#f8c96b'
  },
  academic_architect_skill_gap: {
    label: 'Phân Tích Kỹ Năng',
    description: 'So sánh kỹ năng hiện tại với yêu cầu công việc thực tế.',
    icon: FileSearch,
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
    agent: 'profile_scanner',
    title: 'MI Test',
    desc: 'Khám phá nhóm năng lực và kiểu học nổi trội',
    prompt: 'Tôi muốn làm MI Test / Multiple Intelligences để xem nhóm năng lực và kiểu học nào phù hợp với tôi.'
  },
  {
    agent: 'market_scout',
    title: 'Khảo sát thị trường',
    desc: 'Tìm hiểu xu hướng tuyển dụng, yêu cầu và mức lương',
    prompt: 'Tôi muốn khảo sát thị trường cho vị trí Python Backend Developer. Hiện tại nhu cầu tuyển dụng, kỳ vọng lương và các framework quan trọng nhất là gì?'
  },
  {
    agent: 'academic_architect_create_gantt',
    title: 'Dựng lộ trình học',
    desc: 'Tạo các bước học để lấp khoảng trống mục tiêu',
    prompt: 'Tôi muốn xây dựng lộ trình học tập.'
  },
  {
    agent: 'profile_scanner',
    title: 'Tư vấn tổng hợp',
    desc: 'Đối chiếu CV, Holland và MI để kiểm tra định hướng',
    prompt: 'Hãy tổng hợp CV, Holland và MI của tôi để kiểm tra định hướng nghề nghiệp có đang xung đột hay không.'
  }
];

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
    const isAssessmentOutput = output?.feature === 'holland_assessment' || output?.feature === 'assessment';
    const hasProfileAction = output?.feature === 'profile_scan'
      && Array.isArray(output?.profile_action?.options)
      && output.profile_action.options.length > 0;
    return (isAssessmentOutput
      && (output?.questions || output?.top_code || output?.top_dimensions || output?.result_code))
      || hasProfileAction
      || output?.feature === 'profile_confirmation'
      || output?.feature === 'career_alignment';
  });
}

function getVisibleToolCalls(toolCalls = []) {
  const hasSuccessfulHollandResult = toolCalls.some((toolCall) => {
    const output = normalizeToolOutput(toolCall.output);
    const isAssessmentOutput = output?.feature === 'holland_assessment' || output?.feature === 'assessment';
    return isAssessmentOutput && (output?.top_code || output?.top_dimensions || output?.result_code);
  });

  if (!hasSuccessfulHollandResult) return toolCalls;

  return toolCalls.filter((toolCall) => {
    const output = normalizeToolOutput(toolCall.output);
    const isAssessmentOutput = output?.feature === 'holland_assessment' || output?.feature === 'assessment';
    const isSupersededHollandError = isAssessmentOutput
      && (output?.status === 'error' || output?.error)
      && !output?.questions
      && !output?.top_code
      && !output?.top_dimensions
      && !output?.result_code;
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

const multipleIntelligenceLabels = {
  linguistic: 'Ngôn ngữ',
  logical_math: 'Logic / Toán học',
  spatial: 'Không gian / Hình ảnh',
  bodily_kinesthetic: 'Vận động / Thực hành',
  musical: 'Âm nhạc / Nhịp điệu',
  interpersonal: 'Giao tiếp / Thấu hiểu người khác',
  intrapersonal: 'Tự nhận thức',
  naturalistic: 'Thiên nhiên / Phân loại hệ thống'
};

const localizedRiasecLabels = {
  vi: { R: 'Thực tế', I: 'Nghiên cứu', A: 'Nghệ thuật', S: 'Xã hội', E: 'Dẫn dắt', C: 'Quy củ' },
  en: { R: 'Realistic', I: 'Investigative', A: 'Artistic', S: 'Social', E: 'Enterprising', C: 'Conventional' }
};
void riasecLabels;
void multipleIntelligenceLabels;

const localizedMiLabels = {
  vi: { linguistic: 'Ngôn ngữ', logical_math: 'Logic / Toán học', spatial: 'Không gian / Hình ảnh', bodily_kinesthetic: 'Vận động / Thực hành', musical: 'Âm nhạc / Nhịp điệu', interpersonal: 'Giao tiếp / Thấu hiểu người khác', intrapersonal: 'Tự nhận thức', naturalistic: 'Thiên nhiên / Phân loại hệ thống' },
  en: { linguistic: 'Linguistic', logical_math: 'Logical / Mathematical', spatial: 'Spatial / Visual', bodily_kinesthetic: 'Bodily / Kinesthetic', musical: 'Musical / Rhythmic', interpersonal: 'Interpersonal', intrapersonal: 'Intrapersonal', naturalistic: 'Naturalistic' }
};

function getAssessmentDisplayConfig(result, locale = 'vi') {
  if (result?.feature === 'assessment') {
    return {
      eyebrow: `Kết quả ${result.title || 'Assessment'}`,
      title: result.result_code || result.top_dimensions?.join(' / ') || result.title || 'Đang cập nhật',
      labels: localizedMiLabels[locale],
      answerUnit: 'câu đã trả lời'
    };
  }

  return {
    eyebrow: 'Kết quả Holland Test',
    title: result?.top_code || 'Đang cập nhật',
    labels: localizedRiasecLabels[locale],
    answerUnit: 'câu đã trả lời'
  };
}

function HollandResultCard({ result, locale = 'vi' }) {
  const scores = result?.scores || {};
  const displayConfig = getAssessmentDisplayConfig(result, locale);
  const displayTitle = result?.feature === 'assessment'
    ? (result?.top_dimensions || []).map((key) => localizedMiLabels[locale][key] || key).join(' / ')
    : result?.top_code;
  const displayEyebrow = result?.feature === 'assessment'
    ? uiText[locale].assessmentResult
    : (locale === 'vi' ? 'Kết quả Holland Test' : 'Holland Test result');
  const answeredCount = result?.answered_count;
  const hasScores = Object.keys(scores).length > 0;

  return (
    <div className="holland-result-card">
      <div className="holland-result-header">
        <div>
          <div className="holland-eyebrow">{displayEyebrow}</div>
          <h3>{displayTitle || displayConfig.title}</h3>
          <p>{result?.interpretation_vi || 'Agent đã ghi nhận kết quả bài test của bạn.'}</p>
        </div>
        {answeredCount && (
          <div className="holland-result-count">
            <strong>{answeredCount}</strong>
            <span>{uiText[locale].answered}</span>
          </div>
        )}
      </div>

      {hasScores && (
        <div className="holland-score-list" aria-label="Điểm assessment">
          {Object.entries(displayConfig.labels).map(([code, label]) => {
            const score = Number(scores[code] || 0);
            const percent = Math.round(score * 100);
            return (
              <div className="holland-score-row" key={code}>
                <div className="holland-score-meta">
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

      {Array.isArray(result?.recommendations_vi) && result.recommendations_vi.length > 0 && (
        <div className="profile-scan-grid">
          <div>
            <span className="profile-scan-section-title">Gợi ý học tập</span>
            <ul className="profile-recommendations">
              {result.recommendations_vi.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function ProfileConfirmationActions({ action, onSendMessage }) {
  const [submitting, setSubmitting] = useState('');
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState('');
  const options = Array.isArray(action?.options) ? action.options : [];

  if (!options.length) {
    return action?.message_vi ? (
      <div className="profile-action-status"><CheckCircle2 size={16} />{action.message_vi}</div>
    ) : null;
  }

  const handleDecision = async (option) => {
    if (submitting || completed) return;
    const displayText = option.decision === 'reject'
      ? 'Không, hãy giữ nguyên hồ sơ cá nhân hiện tại.'
      : `${option.label_vi} từ CV vừa tải lên.`;
    const backendText = [
      displayText,
      `Call profile_scanner immediately with task="profile_confirm", cv_document_id="${action.cv_document_id}", and decision="${option.decision}".`,
      'Do not ask for confirmation again and do not change the decision.'
    ].join('\n');
    setSubmitting(option.decision);
    setError('');
    const ok = await onSendMessage({ displayText, backendText });
    setSubmitting('');
    if (ok) setCompleted(true);
    else setError('Chưa cập nhật được hồ sơ. Vui lòng kiểm tra kết nối và thử lại.');
  };

  return (
    <div className="profile-confirmation-panel">
      <div>
        <span className="profile-scan-section-title">Xác nhận hồ sơ cá nhân</span>
        <p>{action.message_vi}</p>
      </div>
      <div className="profile-confirmation-actions">
        {options.map((option, index) => (
          <button
            key={option.decision}
            className={index === 0 ? 'primary' : 'secondary'}
            disabled={Boolean(submitting) || completed}
            onClick={() => handleDecision(option)}
            type="button"
          >
            {submitting === option.decision ? 'Đang xử lý...' : option.label_vi}
          </button>
        ))}
      </div>
      {completed && <div className="profile-action-status"><CheckCircle2 size={16} />Đã gửi lựa chọn.</div>}
      {error && <div className="holland-form-error">{error}</div>}
    </div>
  );
}

function ProfileScanResultCard({ result, onSendMessage, locale = 'vi' }) {
  const hasGrade = Boolean(result?.grade) && result?.total_score !== null && result?.total_score !== undefined;
  const grade = result?.grade || 'N/A';
  const dimensions = Array.isArray(result?.score_dimensions) ? result.score_dimensions : [];
  const skills = Array.isArray(result?.extracted_skills) ? result.extracted_skills : [];
  const recommendations = Array.isArray(result?.recommendations) ? result.recommendations.map((item) => localizeRecommendation(item, locale)) : [];
  const strengths = Array.isArray(result?.strengths) ? result.strengths : [];
  const resultSummary = getCvScoreCopy(grade, locale);

  return (
    <div className="profile-scan-card">
      <div className="profile-scan-header">
        <div className={`profile-rank-mark rank-${grade.toLowerCase().replace('/', '-')}`}>
          <span>{grade}</span>
        </div>
        <div className="profile-scan-title">
          <div className="profile-scan-eyebrow">{locale === 'vi' ? 'Kết quả đánh giá CV' : 'CV assessment result'}</div>
          <h3>{result?.target_role || 'Profile Scanner'}</h3>
          <p>{resultSummary}</p>
        </div>
        <div className="profile-total-score">
          <strong>{hasGrade ? Math.round(Number(result.total_score)) : '--'}</strong>
          <span>{hasGrade ? '/100' : 'chưa chấm'}</span>
        </div>
      </div>

      {dimensions.length > 0 && (
        <div className="profile-dimension-list">
          {dimensions.map((dimension) => {
            const score = Math.round(Number(dimension.score || 0));
            return (
              <div className="profile-dimension-row" key={dimension.key || dimension.label}>
                <div className="profile-dimension-meta">
                  <strong>{scoreDimensionLabels[locale][dimension.key] || dimension.label}</strong>
                  <span>{score}/100</span>
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
          <span className="profile-scan-section-title">{locale === 'vi' ? 'Kỹ năng nổi bật' : 'Highlighted skills'}</span>
          <div className="profile-skill-cloud">
            {skills.slice(0, 12).map((skill) => <span key={skill}>{skill}</span>)}
            {!skills.length && <em>Chưa phát hiện kỹ năng rõ ràng.</em>}
          </div>
        </div>
        <div>
          <span className="profile-scan-section-title">{locale === 'vi' ? 'Ưu tiên cải thiện' : 'Improvement priorities'}</span>
          <ul className="profile-recommendations">
            {recommendations.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
            {!recommendations.length && strengths.slice(0, 3).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      </div>
      {result?.profile_action && (
        <ProfileConfirmationActions action={result.profile_action} onSendMessage={onSendMessage} />
      )}
    </div>
  );
}

function CareerAlignmentCard({ result }) {
  const stateLabels = {
    aligned: 'Định hướng phù hợp',
    interest_conflict: 'Xung đột về hứng thú',
    readiness_gap: 'Thiếu bằng chứng sẵn sàng',
    exploration_advised: 'Nên khám phá thêm',
    mixed_or_uncertain: 'Chưa đủ rõ ràng',
    insufficient_data: 'Thiếu dữ liệu'
  };
  const recommendations = Array.isArray(result?.recommendations_vi) ? result.recommendations_vi : [];
  return (
    <div className="career-alignment-card">
      <div className="career-alignment-header">
        <div>
          <span className="profile-scan-eyebrow">Career Alignment · {result?.rule_version}</span>
          <h3>{stateLabels[result?.alignment_state] || stateLabels.insufficient_data}</h3>
          <p>{result?.target_role || 'Chưa xác định target role'}</p>
        </div>
        {result?.career_alignment_score !== null && result?.career_alignment_score !== undefined && (
          <div className="profile-total-score"><strong>{Math.round(result.career_alignment_score)}</strong><span>/100</span></div>
        )}
      </div>
      <div className="alignment-metrics">
        <span>CV readiness <strong>{result?.cv_readiness_score ?? '--'}</strong></span>
        <span>Holland alignment <strong>{result?.holland_alignment_score ?? '--'}</strong></span>
        <span>Conflict <strong>{result?.conflict_severity || 'unknown'}</strong></span>
      </div>
      {recommendations.length > 0 && <ul className="profile-recommendations">{recommendations.map((item) => <li key={item}>{item}</li>)}</ul>}
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
  const isGenericAssessment = output?.feature === 'assessment';
  const assessmentType = output?.assessment_type || 'holland_riasec';
  const assessmentTitle = output?.title || 'Holland Test';
  const assessmentEyebrow = output?.eyebrow_vi || 'Bài đánh giá RIASEC';
  const assessmentDescription = output?.description_vi || 'Chọn mức độ giống bạn từ 1 đến 5. Kết quả sẽ được agent chấm điểm và lưu vào hồ sơ định hướng nghề nghiệp.';
  const attemptId = output?.attempt_id || '';
  const answeredCount = Object.keys(answers).length;
  const isComplete = answeredCount === questions.length;

  if (!questions.length) return null;

  const handleSubmit = async () => {
    if (!isComplete || submitted || submitting) return;
    const payload = questions.map((question) => ({
      question_id: question.id,
      score: answers[question.id]
    }));
    const displayText = isGenericAssessment
      ? `Mình đã hoàn thành ${assessmentTitle} với ${questions.length} câu trả lời. Hãy chấm điểm và lưu kết quả vào hồ sơ của mình.`
      : `Mình đã hoàn thành Holland Test với ${questions.length} câu trả lời. Hãy chấm điểm và lưu kết quả RIASEC vào hồ sơ của mình.`;
    const backendText = isGenericAssessment
      ? [
        `Mình đã hoàn thành ${assessmentTitle}. Hãy chấm điểm bằng profile_scanner tool với task="assessment_score", assessment_type="${assessmentType}", attempt_id="${attemptId}" và answers_json sau:`,
        '```json',
        JSON.stringify(payload, null, 2),
        '```'
      ].join('\n')
      : [
        `Mình đã hoàn thành Holland Test. Hãy chấm điểm bằng profile_scanner tool với task="holland_score", attempt_id="${attemptId}" và answers_json sau:`,
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
          <div className="holland-eyebrow">{assessmentEyebrow}</div>
          <h3>{assessmentTitle}</h3>
          <p>{assessmentDescription}</p>
        </div>
        <div className="holland-progress">
          <strong>{answeredCount}/{questions.length}</strong>
          <span>đã trả lời</span>
        </div>
      </div>

      {latestResult && (
        <div className="holland-latest">
          <span>Kết quả gần nhất</span>
          <strong>{latestResult.top_code || latestResult.result_code || latestResult.top_dimensions?.join(' / ')}</strong>
          <small>{latestResult.interpretation_vi}</small>
        </div>
      )}

      <div className="holland-scale">
        <span>1 - {output?.scale?.['1'] || 'Rất không giống'}</span>
        <span>3 - {output?.scale?.['3'] || 'Trung lập'}</span>
        <span>5 - {output?.scale?.['5'] || 'Rất giống'}</span>
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

  const [calendarStatus, setCalendarStatus] = useState('idle'); // 'idle' | 'generating' | 'preview' | 'success' | 'error'
  const [calendarMessage, setCalendarMessage] = useState('');
  const [proposedEvents, setProposedEvents] = useState([]);

  const handleGenerateSchedule = async () => {
    if (!user || calendarStatus === 'generating') return;
    if (courses.length === 0) return;

    setCalendarStatus('generating');
    setCalendarMessage('');
    try {
      const res = await fetch(`${backendUrl}/calendar/generate-schedule`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': user.google_id
        },
        body: JSON.stringify({
          career_goal: careerGoal,
          lacking_skills: lackingSkills,
          courses: courses.map(c => ({ 
            name: c.name, 
            url: c.url,
            duration: c.duration || '15 giờ',
            workload: c.workload || ''
          }))
        })
      });
      if (!res.ok) throw new Error('Không thể tạo lịch học dự kiến');
      const data = await res.json();
      setProposedEvents(data.events || []);
      setCalendarStatus('preview');
    } catch (err) {
      console.error(err);
      setCalendarStatus('error');
      setCalendarMessage('Không thể tạo lịch học dự kiến. Vui lòng thử lại sau.');
    }
  };

  const expandRecurrentEvents = (events) => {
    const expanded = [];
    
    for (const event of events) {
      const startDt = new Date(event.start.dateTime);
      const endDt = new Date(event.end.dateTime);
      const durationMs = endDt.getTime() - startDt.getTime();
      
      let recurrenceRule = null;
      if (event.recurrence && event.recurrence[0]) {
        recurrenceRule = event.recurrence[0];
      }
      
      if (!recurrenceRule) {
        expanded.push({
          summary: event.summary,
          description: event.description,
          startDate: startDt,
          endDate: endDt
        });
        continue;
      }
      
      const parts = recurrenceRule.replace("RRULE:", "").split(";");
      const ruleObj = {};
      for (const part of parts) {
        const [key, val] = part.split("=");
        if (key && val) {
          ruleObj[key] = val;
        }
      }
      
      const freq = ruleObj.FREQ;
      const count = parseInt(ruleObj.COUNT) || 1;
      
      if (freq === 'DAILY') {
        let currentDate = new Date(startDt);
        for (let i = 0; i < count; i++) {
          const occurrenceStart = new Date(currentDate);
          const occurrenceEnd = new Date(occurrenceStart.getTime() + durationMs);
          expanded.push({
            summary: event.summary,
            description: event.description,
            startDate: occurrenceStart,
            endDate: occurrenceEnd
          });
          currentDate.setDate(currentDate.getDate() + 1);
        }
      } else if (freq === 'WEEKLY') {
        const byDay = ruleObj.BYDAY ? ruleObj.BYDAY.split(",") : [];
        const dayMap = { 'SU': 0, 'MO': 1, 'TU': 2, 'WE': 3, 'TH': 4, 'FR': 5, 'SA': 6 };
        const targetDays = byDay.map(d => dayMap[d]);
        
        let currentDate = new Date(startDt);
        let occurrencesGenerated = 0;
        const maxAttempts = 1000;
        let attempts = 0;
        
        while (occurrencesGenerated < count && attempts < maxAttempts) {
          attempts++;
          const currentDayOfWeek = currentDate.getDay();
          if (targetDays.length === 0 || targetDays.includes(currentDayOfWeek)) {
            const occurrenceStart = new Date(currentDate);
            const occurrenceEnd = new Date(occurrenceStart.getTime() + durationMs);
            expanded.push({
              summary: event.summary,
              description: event.description,
              startDate: occurrenceStart,
              endDate: occurrenceEnd
            });
            occurrencesGenerated++;
          }
          currentDate.setDate(currentDate.getDate() + 1);
        }
      } else {
        expanded.push({
          summary: event.summary,
          description: event.description,
          startDate: startDt,
          endDate: endDt
        });
      }
    }
    
    return expanded;
  };

  const handleExportToCSV = () => {
    if (proposedEvents.length === 0) return;

    try {
      const expandedEvents = expandRecurrentEvents(proposedEvents);
      
      const headers = ['Subject', 'Start Date', 'Start Time', 'End Date', 'End Time', 'All Day Event', 'Description'];
      
      const rows = expandedEvents.map(event => {
        const sDate = event.startDate;
        const eDate = event.endDate;
        
        const pad = (num) => String(num).padStart(2, '0');
        const formatDate = (d) => `${pad(d.getMonth() + 1)}/${pad(d.getDate())}/${d.getFullYear()}`;
        
        const formatTime = (d) => {
          let hours = d.getHours();
          const minutes = pad(d.getMinutes());
          const ampm = hours >= 12 ? 'PM' : 'AM';
          hours = hours % 12;
          hours = hours ? hours : 12;
          return `${pad(hours)}:${minutes} ${ampm}`;
        };
        
        const subject = event.summary;
        const startDate = formatDate(sDate);
        const startTime = formatTime(sDate);
        const endDate = formatDate(eDate);
        const endTime = formatTime(eDate);
        const allDayEvent = 'False';
        const description = event.description || '';
        
        const escapeCsv = (str) => {
          const clean = str.replace(/"/g, '""');
          return `"${clean}"`;
        };
        
        return [
          escapeCsv(subject),
          escapeCsv(startDate),
          escapeCsv(startTime),
          escapeCsv(endDate),
          escapeCsv(endTime),
          escapeCsv(allDayEvent),
          escapeCsv(description)
        ].join(',');
      });
      
      const csvContent = "\ufeff" + [headers.join(','), ...rows].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      
      const link = document.createElement("a");
      link.setAttribute("href", url);
      const filename = `Lịch_Học_Tập_${careerGoal.replace(/\s+/g, '_')}.csv`;
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      setCalendarStatus('success');
      setCalendarMessage('Đã tải xuống file CSV lịch thành công! Bạn có thể nhập file này vào Google Calendar (Cài đặt -> Nhập & xuất -> Chọn file từ máy tính) để thêm toàn bộ lộ trình học.');
    } catch (err) {
      console.error(err);
      setCalendarStatus('error');
      setCalendarMessage('Không thể tạo và tải xuống file CSV. Vui lòng thử lại sau.');
    }
  };

  const handleCancelPreview = () => {
    setCalendarStatus('idle');
    setProposedEvents([]);
    setCalendarMessage('');
  };

  const handleEventChange = (index, field, value) => {
    const updated = [...proposedEvents];
    const ev = { ...updated[index] };

    if (field === 'summary') {
      ev.summary = value;
    } else if (field === 'description') {
      ev.description = value;
    } else if (field === 'startDate') {
      const startRest = ev.start.dateTime.substring(10);
      const endRest = ev.end.dateTime.substring(10);
      ev.start = { ...ev.start, dateTime: value + startRest };
      ev.end = { ...ev.end, dateTime: value + endRest };
    } else if (field === 'pattern') {
      let count = 1;
      if (ev.recurrence && ev.recurrence[0]) {
        const match = ev.recurrence[0].match(/COUNT=(\d+)/);
        if (match) {
          count = parseInt(match[1]);
        }
      }
      if (value === 'weekly') {
        ev.recurrence = [`RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=${count}`];
      } else if (value === 'daily') {
        ev.recurrence = [`RRULE:FREQ=DAILY;COUNT=${count}`];
      } else {
        ev.recurrence = [];
      }
    } else if (field === 'count') {
      const countVal = parseInt(value) || 1;
      if (ev.recurrence && ev.recurrence[0]) {
        const parts = ev.recurrence[0].split(';');
        const newParts = parts.map(p => {
          if (p.startsWith('COUNT=')) {
            return `COUNT=${countVal}`;
          }
          return p;
        });
        if (!newParts.some(p => p.startsWith('COUNT='))) {
          newParts.push(`COUNT=${countVal}`);
        }
        ev.recurrence = [newParts.join(';')];
      }
    }
    
    updated[index] = ev;
    setProposedEvents(updated);
  };

  return (
    <div className="calendar-sync-card">
      <div className="calendar-card-header">
        <span className="calendar-card-icon" role="img" aria-label="calendar">📅</span>
        <h4>Lập kế hoạch học tập</h4>
      </div>
      
      {calendarStatus === 'idle' && (
        <>
          <p className="calendar-card-desc">
            Tải xuống Gantt Chart (Excel) hoặc tạo file CSV để nhập lộ trình học vào Google Calendar.
          </p>
          <div className="calendar-card-actions" style={{ display: 'flex', gap: '10px' }}>
            {output.chart_id && (
              <button 
                className="calendar-sync-btn" 
                style={{ backgroundColor: '#17A2B8', color: 'white' }}
                onClick={() => window.open(`${backendUrl}/chart/${output.chart_id}/excel`, '_blank')}
              >
                Tải Gantt Chart (Excel)
              </button>
            )}
            <button className="calendar-sync-btn" onClick={handleGenerateSchedule} disabled={courses.length === 0}>
              Tạo lịch học (Google Calendar CSV)
            </button>
          </div>
        </>
      )}

      {calendarStatus === 'generating' && (
        <>
          <p className="calendar-card-desc">Đang tạo lịch học đề xuất...</p>
          <div className="calendar-card-actions">
            <button className="calendar-sync-btn loading" disabled>
              <span className="btn-spinner" />
              Đang tạo lịch...
            </button>
          </div>
        </>
      )}

      {calendarStatus === 'preview' && (
        <div className="calendar-preview-container">
          <p className="calendar-preview-heading">Xem trước & Tùy chỉnh lịch học của bạn:</p>
          {proposedEvents.map((event, idx) => {
            const startDate = event.start.dateTime.substring(0, 10);
            
            let pattern = 'none';
            let count = 1;
            if (event.recurrence && event.recurrence[0]) {
              if (event.recurrence[0].includes('FREQ=WEEKLY')) pattern = 'weekly';
              else if (event.recurrence[0].includes('FREQ=DAILY')) pattern = 'daily';
              else pattern = 'custom';
              
              const match = event.recurrence[0].match(/COUNT=(\d+)/);
              if (match) count = parseInt(match[1]);
            }

            return (
              <div key={idx} className="calendar-event-edit-card">
                <div className="form-group">
                  <label>Tên sự kiện</label>
                  <input 
                    type="text" 
                    value={event.summary} 
                    onChange={(e) => handleEventChange(idx, 'summary', e.target.value)} 
                  />
                </div>
                
                <div className="form-row">
                  <div className="form-group">
                    <label>Ngày bắt đầu</label>
                    <input 
                      type="date" 
                      value={startDate} 
                      onChange={(e) => handleEventChange(idx, 'startDate', e.target.value)} 
                    />
                  </div>
                  
                  <div className="form-group">
                    <label>Tần suất học</label>
                    <select 
                      value={pattern} 
                      onChange={(e) => handleEventChange(idx, 'pattern', e.target.value)}
                    >
                      <option value="weekly">Hàng tuần (Thứ 2, 4, 6)</option>
                      <option value="daily">Hàng ngày</option>
                      <option value="none">Không lặp lại</option>
                    </select>
                  </div>

                  {pattern !== 'none' && (
                    <div className="form-group">
                      <label>{pattern === 'weekly' ? 'Số buổi học' : 'Số ngày học'}</label>
                      <input 
                        type="number" 
                        min="1" 
                        value={count} 
                        onChange={(e) => handleEventChange(idx, 'count', e.target.value)} 
                      />
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <label>Mô tả chi tiết</label>
                  <textarea 
                    rows="3" 
                    value={event.description} 
                    onChange={(e) => handleEventChange(idx, 'description', e.target.value)} 
                  />
                </div>
              </div>
            );
          })}

          <div className="calendar-card-actions preview-actions">
            <button className="calendar-cancel-btn" onClick={handleCancelPreview}>
              Hủy
            </button>
            <button className="calendar-sync-btn confirm-sync-btn" onClick={handleExportToCSV}>
              Tải xuống file CSV
            </button>
          </div>
        </div>
      )}

      {calendarStatus === 'success' && (
        <div className="calendar-sync-success-msg" style={{ width: '100%', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span className="success-check">✓</span>
            <span>{calendarMessage}</span>
          </div>
          <button className="calendar-cancel-btn" onClick={handleCancelPreview}>
            Đóng
          </button>
        </div>
      )}

      {calendarStatus === 'error' && (
        <div className="calendar-sync-error-msg">
          <span className="error-cross">✕</span>
          <span>{calendarMessage}</span>
          <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
            <button className="calendar-cancel-btn" onClick={handleCancelPreview}>
              Quay lại
            </button>
            <button className="calendar-retry-btn" onClick={proposedEvents.length > 0 ? handleExportToCSV : handleGenerateSchedule}>
              Thử lại
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ToolCallWidget({ toolName, output, status, onSendMessage, resolvedProfileDocuments, locale = 'vi' }) {
  const [expanded, setExpanded] = useState(true);
  const info = agentInfo[toolName] || {
    label: toolName,
    icon: Terminal,
    themeClass: 'default'
  };
  const Icon = info.icon;
  const normalizedOutput = normalizeToolOutput(output);
  const isHollandOutput = normalizedOutput?.feature === 'holland_assessment';
  const isAssessmentOutput = normalizedOutput?.feature === 'assessment';
  const isProfileScanOutput = normalizedOutput?.feature === 'profile_scan';
  const isProfileConfirmationOutput = normalizedOutput?.feature === 'profile_confirmation';
  const isCareerAlignmentOutput = normalizedOutput?.feature === 'career_alignment';
  const shouldRenderHollandForm = (isHollandOutput || isAssessmentOutput)
    && normalizedOutput?.questions
    && status === 'completed';
  const shouldRenderHollandResult = (isHollandOutput || isAssessmentOutput)
    && (normalizedOutput?.top_code || normalizedOutput?.top_dimensions || normalizedOutput?.result_code)
    && status === 'completed';
  const shouldRenderProfileScanResult = isProfileScanOutput
    && status === 'completed';
  const shouldRenderVerifier = toolName === 'academic_architect_input_verifier'
    && status === 'completed';
  const profileActionResolved = isProfileScanOutput
    && resolvedProfileDocuments?.has(normalizedOutput?.profile_action?.cv_document_id);
  const profileScanResult = profileActionResolved
    ? {
      ...normalizedOutput,
      profile_action: {
        ...normalizedOutput.profile_action,
        options: [],
        message_vi: 'Lựa chọn cho CV này đã được xử lý.'
      }
    }
    : normalizedOutput;
  const toolLabel = (isHollandOutput || isAssessmentOutput) && toolName === 'profile_scanner'
    ? `${info.label} · ${normalizedOutput?.title || 'Assessment'}`
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
                <HollandResultCard result={normalizedOutput} locale={locale} />
              ) : shouldRenderProfileScanResult ? (
                <ProfileScanResultCard result={profileScanResult} onSendMessage={onSendMessage} locale={locale} />
              ) : isCareerAlignmentOutput && status === 'completed' ? (
                <CareerAlignmentCard result={normalizedOutput} />
              ) : isProfileConfirmationOutput && status === 'completed' ? (
                <div className="profile-action-status"><CheckCircle2 size={16} />{normalizedOutput?.message_vi}</div>
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
      <div className="login-visual" aria-hidden="true" />
      <header className="login-brand">
        <img src={brandMarkSrc} alt="" />
        <span>
          <strong>Z-MentorAI</strong>
          <small>Cố vấn nghề nghiệp AI</small>
        </span>
      </header>

      <main className="login-shell">
        <section className="login-hero">
          <div className="login-kicker">Hồ sơ rõ ràng. Quyết định có cơ sở.</div>
          <h1>Hiểu rõ hồ sơ.<br />Chọn đúng bước tiếp theo.</h1>
          <p>
            Z-MentorAI kết nối hồ sơ, tín hiệu thị trường và mục tiêu học tập để mỗi quyết định nghề nghiệp
            đều có cơ sở rõ ràng.
          </p>

          <div className="login-card">
            <div className="login-card-heading">
              <span>Bắt đầu phiên tư vấn</span>
              <small>Thông tin của bạn được giữ theo từng tài khoản.</small>
            </div>
            <div className="login-actions">
              <div id="google-signin-button" className="google-btn-container"></div>
              {!googleClientId && (
                <div className="login-config-note">Đang chờ cấu hình đăng nhập Google.</div>
              )}
            </div>
          </div>

          <div className="login-capabilities" aria-label="Các năng lực chính">
            <div>
              <FileSearch size={18} />
              <span><strong>Quét hồ sơ</strong><small>Đọc bằng chứng và khoảng trống</small></span>
            </div>
            <div>
              <Compass size={18} />
              <span><strong>Hiểu thị trường</strong><small>Đối chiếu nhu cầu tuyển dụng</small></span>
            </div>
            <div>
              <GraduationCap size={18} />
              <span><strong>Dựng lộ trình</strong><small>Chuyển mục tiêu thành hành động</small></span>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function AccountHeader({ activeAgents, avatarSrc, user, locale, onNavigate, onAvatarClick, onLogout }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);
  const t = uiText[locale];

  useEffect(() => {
    const close = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = (event) => event.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, []);

  return (
    <header className="app-header">
      <button className="brand-section brand-button" onClick={() => onNavigate('chat')} type="button">
        <span className="brand-logo"><img src={brandMarkSrc} alt="" /></span>
        <span><strong className="brand-title">Z-MentorAI</strong><span className="brand-subtitle">Cố vấn nghề nghiệp AI</span></span>
      </button>
      <div className="agent-status-bar">
        {Object.keys(agentInfo).slice(0, 3).map((key) => (
          <div className={`agent-badge ${activeAgents.includes(key) ? 'active' : ''}`} key={key}>
            <span className="badge-dot" /><span>{agentInfo[key].label}</span>
          </div>
        ))}
      </div>
      <div className="account-menu" ref={menuRef}>
        <button className="account-trigger" aria-expanded={open} onClick={() => setOpen((value) => !value)} type="button">
          {avatarSrc ? <img src={avatarSrc} alt="" className="user-avatar" /> : <span className="user-avatar-placeholder"><User size={18} /></span>}
          <span className="user-info"><span className="user-name">{user.name}</span><span className="user-email">{user.email}</span></span>
          <ChevronDown size={16} />
        </button>
        {open && (
          <div className="account-dropdown">
            <button onClick={() => { onNavigate('profile'); setOpen(false); }} type="button"><User size={17} /><span>{t.profile}</span></button>
            <button onClick={() => { onNavigate('settings'); setOpen(false); }} type="button"><Settings size={17} /><span>{t.settings}</span></button>
            <button onClick={() => { onAvatarClick(); setOpen(false); }} type="button"><Upload size={17} /><span>{locale === 'vi' ? 'Đổi ảnh đại diện' : 'Change avatar'}</span></button>
            <div className="account-dropdown-separator" />
            <button className="danger" onClick={onLogout} type="button"><LogOut size={17} /><span>{t.logout}</span></button>
          </div>
        )}
      </div>
    </header>
  );
}

function ProfileWorkspace({ profile, locale, onBack, onSave, loading }) {
  const t = uiText[locale];
  const [form, setForm] = useState(profile || {});
  const [status, setStatus] = useState('');
  const fields = [
    ['name', t.fullName], ['phone', t.phone], ['location', t.location], ['target_role', t.targetRole],
    ['linkedin_url', t.linkedin], ['github_url', t.github], ['portfolio_url', t.portfolio]
  ];
  const save = async (event) => {
    event.preventDefault();
    setStatus('saving');
    const ok = await onSave(form);
    setStatus(ok ? 'saved' : 'error');
  };
  const cv = profile?.current_cv;
  const skills = (cv?.skills || []).map((skill) => typeof skill === 'string' ? skill : (skill[`display_name_${locale}`] || skill.canonical_name));
  return (
    <main className="account-workspace">
      <div className="account-workspace-header"><button onClick={onBack} type="button"><ArrowRight size={17} />{t.backChat}</button><div><h2>{t.personalTitle}</h2><p>{t.personalDesc}</p></div></div>
      <div className="profile-layout">
        <form className="profile-form" onSubmit={save}>
          <label className="profile-field"><span>{t.email}</span><div className="locked-input"><Lock size={15} /><input disabled value={profile?.email || ''} /></div></label>
          {fields.map(([key, label]) => <label className="profile-field" key={key}><span>{label}</span><input value={form[key] || ''} onChange={(event) => setForm((value) => ({ ...value, [key]: event.target.value }))} /></label>)}
          <div className="profile-save-row"><button disabled={loading || status === 'saving'} type="submit">{status === 'saving' ? t.saving : t.save}</button>{status === 'saved' && <span><CheckCircle2 size={16} />{t.saved}</span>}{status === 'error' && <span className="form-error">{locale === 'vi' ? 'Không thể lưu thông tin.' : 'Could not save profile.'}</span>}</div>
        </form>
        <section className="current-cv-panel">
          <div className="current-cv-title"><FileText size={20} /><div><span>{t.currentCv}</span><strong>{cv?.original_filename || t.noCv}</strong></div>{cv?.grade && <span className={`cv-grade grade-${String(cv.grade).toLowerCase()}`}>{cv.grade}</span>}</div>
          {cv && <><div className="cv-facts"><div><span>{t.uploadDate}</span><strong>{cv.uploaded_at ? new Date(cv.uploaded_at).toLocaleDateString(locale === 'vi' ? 'vi-VN' : 'en-US') : '--'}</strong></div><div><span>{t.version}</span><strong>v{cv.profile_version || 1}</strong></div><div><span>{locale === 'vi' ? 'Điểm CV' : 'CV score'}</span><strong>{cv.total_score ? `${Math.round(cv.total_score)}/100` : '--'}</strong></div></div>{cv.summary && <p className="cv-summary">{cv.summary}</p>}<div className="profile-skill-cloud">{skills.slice(0, 16).map((skill) => <span key={skill}>{skill}</span>)}</div></>}
        </section>
      </div>
    </main>
  );
}

function SettingsWorkspace({ locale, theme, onBack, onChange }) {
  const t = uiText[locale];
  return <main className="account-workspace settings-workspace"><div className="account-workspace-header"><button onClick={onBack} type="button"><ArrowRight size={17} />{t.backChat}</button><div><h2>{t.settings}</h2><p>{t.settingsDesc}</p></div></div><section className="settings-list"><div className="setting-row"><div><strong>{t.language}</strong><span>Vietnamese / English</span></div><div className="segmented-control"><button className={locale === 'vi' ? 'active' : ''} onClick={() => onChange('language', 'vi')} type="button">VI</button><button className={locale === 'en' ? 'active' : ''} onClick={() => onChange('language', 'en')} type="button">EN</button></div></div><div className="setting-row"><div><strong>{t.appearance}</strong><span>{locale === 'vi' ? 'Chọn chế độ hiển thị phù hợp.' : 'Choose a comfortable display mode.'}</span></div><div className="segmented-control"><button className={theme === 'light' ? 'active' : ''} onClick={() => onChange('theme', 'light')} type="button"><Sun size={15} />{t.light}</button><button className={theme === 'dark' ? 'active' : ''} onClick={() => onChange('theme', 'dark')} type="button"><Moon size={15} />{t.dark}</button></div></div></section></main>;
}

// eslint-disable-next-line no-unused-vars
function LegacyAppHeader({ activeAgents, avatarSrc, user, onAvatarClick, onLogout }) {
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

function WelcomeState({ onSendMessage }) {
  return (
    <div className="welcome-container">
      <img className="welcome-brand-watermark" src={brandMarkSrc} alt="" aria-hidden="true" />
      <div className="welcome-copy">
        <h2>Hãy bắt đầu cùng Z-MentorAI</h2>
        <p>
          Hãy đặt câu hỏi trực tiếp, đính kèm CV hoặc bắt đầu bằng một gợi ý bên dưới.
        </p>
      </div>

      <div className="suggested-heading">Bắt đầu nhanh</div>
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

function MessagesFeed({ messages, isLoading, activeAgents, messagesEndRef, onSendMessage, user, backendUrl, locale = 'vi' }) {
  const resolvedProfileDocuments = new Set(
    messages.flatMap((message) => (message.toolCalls || []).map((toolCall) => normalizeToolOutput(toolCall.output)))
      .filter((output) => output?.feature === 'profile_confirmation' && output?.cv_document_id)
      .map((output) => output.cv_document_id)
  );
  return (
    <div className="messages-feed">
      {messages.map((msg) => {
        const visibleToolCalls = getVisibleToolCalls(msg.toolCalls || []);
        const hideAssistantContent = msg.role === 'assistant'
          && hasHollandInteractiveToolCall(visibleToolCalls);

        return (
          <div key={msg.id} className={`message-wrapper ${msg.role}`}>
            <div className="message-header">{msg.role === 'user' ? 'Bạn' : 'Điều phối viên'}</div>

            {msg.role === 'assistant' && visibleToolCalls.filter(toolCall => toolCall.name !== 'academic_architect_create_gantt').map((toolCall) => (
              <ToolCallWidget
                key={toolCall.id}
                toolName={toolCall.name}
                input={toolCall.input}
                output={toolCall.output}
                status={toolCall.status}
                onSendMessage={onSendMessage}
                user={user}
                backendUrl={backendUrl}
                resolvedProfileDocuments={resolvedProfileDocuments}
                locale={locale}
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
                    {(() => {
                      const academicToolCall = msg.toolCalls?.find(
                        (t) => t.name === 'academic_architect_create_gantt' && t.status === 'completed'
                      );
                      const output = academicToolCall ? normalizeToolOutput(academicToolCall.output) : null;
                      const courses = output ? [
                        ...(output.courses || []),
                        ...(output.alternative_courses || [])
                      ] : [];

                      return (
                        <ReactMarkdown
                          components={{
                            a: ({ href, children, ...props }) => {
                              const matchedCourse = courses.find(c => {
                                if (!c.url || !href) return false;
                                const cleanHref = href.toLowerCase().replace(/\/$/, "");
                                const cleanCourseUrl = c.url.toLowerCase().replace(/\/$/, "");
                                return cleanHref === cleanCourseUrl || (c.slug && cleanHref.endsWith(c.slug.toLowerCase()));
                              });

                              if (matchedCourse) {
                                return (
                                  <a
                                    href={matchedCourse.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="markdown-course-link-card"
                                    {...props}
                                  >
                                    <span className="markdown-course-link-icon" role="img" aria-label="course">🎓</span>
                                    <div className="markdown-course-link-content">
                                      <div className="markdown-course-link-title">{matchedCourse.name || children}</div>
                                      <div className="markdown-course-link-duration">⏱️ {matchedCourse.duration || '15 giờ'}</div>
                                    </div>
                                    <div className="markdown-course-link-action">
                                      <span>Học ngay</span>
                                      <ArrowRight size={14} />
                                    </div>
                                  </a>
                                );
                              }

                              return (
                                <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                                  {children}
                                </a>
                              );
                            }
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      );
                    })()}
                    {(() => {
                      const academicToolCall = msg.toolCalls?.find(
                        (t) => t.name === 'academic_architect_create_gantt' && t.status === 'completed'
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
  backendUrl,
  locale = 'vi'
}) {
  return (
    <div className="chat-area">
      {messages.length === 0 ? (
        <WelcomeState onSendMessage={onSendMessage} />
      ) : (
        <MessagesFeed
          messages={messages}
          isLoading={isLoading}
          activeAgents={activeAgents}
          messagesEndRef={messagesEndRef}
          onSendMessage={onSendMessage}
          user={user}
          backendUrl={backendUrl}
          locale={locale}
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
  const [workspace, setWorkspace] = useState('chat');
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [preferences, setPreferences] = useState(() => ({
    language: localStorage.getItem('z_mentor_language') || 'vi',
    theme: localStorage.getItem('z_mentor_theme') || 'light'
  }));

  const backendUrl = useMemo(() => import.meta.env.VITE_API_URL || window.location.origin, []);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const avatarInputRef = useRef(null);
  const cvInputRef = useRef(null);
  const bootstrappedSessionsRef = useRef(null);
  const locale = preferences.language;

  useEffect(() => {
    document.documentElement.dataset.theme = preferences.theme;
    document.documentElement.lang = preferences.language;
    localStorage.setItem('z_mentor_language', preferences.language);
    localStorage.setItem('z_mentor_theme', preferences.theme);
  }, [preferences]);

  const fetchProfile = useCallback(async () => {
    if (!user) return;
    setProfileLoading(true);
    try {
      const response = await fetch(`${backendUrl}/me/profile`, { headers: { 'X-User-Id': user.google_id } });
      if (!response.ok) throw new Error('Unable to load profile');
      const data = await response.json();
      setProfile(data);
      if (data.preferences) setPreferences(data.preferences);
    } catch (error) {
      console.error(error);
    } finally {
      setProfileLoading(false);
    }
  }, [backendUrl, user]);

  useEffect(() => { fetchProfile(); }, [fetchProfile]);

  const saveProfile = async (form) => {
    setProfileLoading(true);
    try {
      const response = await fetch(`${backendUrl}/me/profile`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-User-Id': user.google_id }, body: JSON.stringify(form) });
      if (!response.ok) return false;
      const data = await response.json();
      setProfile(data);
      const nextUser = { ...user, name: data.name };
      setUser(nextUser);
      localStorage.setItem('z_mentor_user', JSON.stringify(nextUser));
      return true;
    } finally { setProfileLoading(false); }
  };

  const updatePreference = async (key, value) => {
    const next = { ...preferences, [key]: value };
    setPreferences(next);
    try {
      await fetch(`${backendUrl}/me/settings`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-User-Id': user.google_id }, body: JSON.stringify(next) });
    } catch (error) { console.error(error); }
  };

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
              const existingLegacyCall = !data.tool_call_id
                ? Array.from(streamedToolCalls.entries()).find(([, call]) => (
                  call.name === data.tool && call.status === 'running'
                ))
                : null;
              const toolCallKey = data.tool_call_id || existingLegacyCall?.[0] || `${data.tool}-${Date.now()}`;
              streamedToolCalls.set(toolCallKey, {
                id: toolCallKey,
                name: data.tool,
                input: data.input,
                status: 'running'
              });
              setActiveAgents((prev) => [...new Set([...prev, data.tool])]);
              setMessages((prev) => prev.map((msg) => {
                if (msg.id !== assistantMessageId) return msg;
                const exists = msg.toolCalls.some((toolCall) => toolCall.id === toolCallKey);
                if (exists) return msg;
                return {
                  ...msg,
                  toolCalls: [...msg.toolCalls, {
                    id: toolCallKey,
                    name: data.tool,
                    input: data.input,
                    status: 'running'
                  }]
                };
              }));
            } else if (data.type === 'tool_end') {
              const existingLegacyCall = !data.tool_call_id
                ? Array.from(streamedToolCalls.entries()).find(([, call]) => (
                  call.name === data.tool && call.status === 'running'
                ))
                : null;
              const toolCallKey = data.tool_call_id || existingLegacyCall?.[0] || `${data.tool}-${Date.now()}`;
              const previousToolCall = streamedToolCalls.get(toolCallKey);
              streamedToolCalls.set(toolCallKey, {
                id: previousToolCall?.id || toolCallKey,
                name: data.tool,
                input: previousToolCall?.input || data.input,
                output: data.output,
                status: 'completed'
              });
              setActiveAgents((prev) => prev.filter((tool) => tool !== data.tool));
              setMessages((prev) => prev.map((msg) => {
                if (msg.id !== assistantMessageId) return msg;
                const existingToolCall = msg.toolCalls.find((toolCall) => toolCall.id === toolCallKey);
                if (!existingToolCall) {
                  return {
                    ...msg,
                    toolCalls: [...msg.toolCalls, {
                      id: toolCallKey,
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
                    toolCall.id === toolCallKey
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
          const existingReplayCall = !data.tool_call_id
            ? Array.from(streamedToolCalls.entries()).find(([, call]) => call.name === data.tool)
            : null;
          const toolCallKey = data.tool_call_id || existingReplayCall?.[0] || `legacy-${data.tool}`;
          if (data.type === 'tool_start' && !streamedToolCalls.has(toolCallKey)) {
            streamedToolCalls.set(toolCallKey, {
              id: toolCallKey,
              name: data.tool,
              input: data.input,
              status: 'running'
            });
          }
          if (data.type === 'tool_end') {
            const previousToolCall = streamedToolCalls.get(toolCallKey);
            streamedToolCalls.set(toolCallKey, {
              id: previousToolCall?.id || toolCallKey,
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
            const existingIndex = mergedToolCalls.findIndex((item) => item.id === toolCall.id);
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
        <AccountHeader
          activeAgents={activeAgents}
          avatarSrc={avatarSrc}
          user={user}
          onAvatarClick={handleAvatarClick}
          onLogout={handleLogout}
          locale={locale}
          onNavigate={setWorkspace}
        />

      {workspace === 'profile' ? (
        <ProfileWorkspace key={`${profile?.user_id || 'profile'}-${profile?.current_cv?.profile_version || 0}`} profile={profile} locale={locale} onBack={() => setWorkspace('chat')} onSave={saveProfile} loading={profileLoading} />
      ) : workspace === 'settings' ? (
        <SettingsWorkspace locale={locale} theme={preferences.theme} onBack={() => setWorkspace('chat')} onChange={updatePreference} />
      ) : <main className="chat-main">
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
          locale={locale}
        />
      </main>}

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
