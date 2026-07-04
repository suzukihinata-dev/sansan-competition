const scenarioModes = {
  ready: "ready",
  loading: "loading",
  empty: "empty",
  error: "error",
};

const emptyCourse = {
  courseId: "",
  name: "コース未選択",
  section: "",
  description: "",
  state: "",
  teacherIds: [],
  studentCount: 0,
};

const emptyAssignment = {
  courseWorkId: "",
  courseId: "",
  title: "課題未選択",
  description: "",
  workType: "ASSIGNMENT",
  maxPoints: null,
  dueDate: null,
  dueTime: null,
  state: "",
  materials: [],
  topicId: "",
  hasRubric: false,
};

const workflowSteps = [
  ["login", "ログイン"],
  ["courses", "コース"],
  ["dashboard", "概要"],
  ["assignment", "課題"],
  ["review", "AI確認"],
  ["exports", "出力"],
  ["confirm", "承認"],
];

const app = document.querySelector("#app");
let oauthPollGeneration = 0;
const manualLogoutStorageKey = "sansan-classroom-manual-logout";

const emptyOAuthDialog = {
  open: false,
  intent: "read",
  authorizationUrl: "",
  statusUrl: "",
  errorMessage: "",
};

const state = {
  isLoggedIn: false,
  view: "login",
  scenario: scenarioModes.ready,
  loadingMessage: "",
  courses: [],
  assignments: [],
  assignmentMetrics: {},
  selectedCourseId: "",
  selectedAssignmentId: "",
  agentOutput: null,
  editableValues: {},
  fieldErrors: {},
  selectedOutputs: new Set(["classroom", "markdown"]),
  developerMode: false,
  posted: false,
  postMessage: "",
  postMessageTone: "success",
  oauthDialog: { ...emptyOAuthDialog },
};

state.agentOutput = normalizeAgentOutput(buildPlaceholderOutput());
resetEditableValues();
render();
void bootstrapGoogleSession();

function buildPlaceholderOutput({
  title = "提出状況を取得してください",
  shortSummary = "Google Classroom に接続して、コースと課題を選択してください。",
  recommendedAction = "ログイン後に対象課題を選び、提出状況を取得してください。",
  agentTaskType = "SUBMISSION_ANALYSIS",
} = {}) {
  return {
    schemaVersion: "1.0.0",
    requestId: "",
    generatedAt: "",
    agentTaskType,
    status: "success",
    course: null,
    summary: {
      title,
      shortSummary,
      teacherActionRequired: false,
      recommendedAction,
    },
    gui: {
      cards: [],
      tables: [],
      warnings: [],
      editableFields: [],
    },
    outputs: {
      markdown: null,
      pdf: null,
      googleDocument: null,
      classroomReminder: null,
    },
    approval: {
      required: false,
      reason: "",
      actions: [],
    },
    errors: [],
  };
}

function buildLocalErrorOutput({
  title,
  shortSummary,
  recommendedAction,
  errorCode,
  errorMessage,
  agentTaskType = "SUBMISSION_ANALYSIS",
}) {
  const course = selectedCourse();
  return {
    schemaVersion: "1.0.0",
    requestId: "",
    generatedAt: new Date().toISOString(),
    agentTaskType,
    status: "error",
    course: course.courseId ? course : null,
    summary: {
      title,
      shortSummary,
      teacherActionRequired: true,
      recommendedAction,
    },
    gui: {
      cards: [],
      tables: [],
      warnings: [],
      editableFields: [],
    },
    outputs: {
      markdown: null,
      pdf: null,
      googleDocument: null,
      classroomReminder: null,
    },
    approval: {
      required: false,
      reason: "失敗レスポンスのため承認操作はありません。",
      actions: [],
    },
    errors: [
      {
        code: errorCode ?? "CLASSROOM_API_PERMISSION_DENIED",
        message: errorMessage ?? shortSummary,
        recoverable: true,
      },
    ],
  };
}

function normalizeAgentOutput(payload) {
  const input = isObject(payload) ? payload : {};
  const summary = isObject(input.summary) ? input.summary : {};
  const gui = isObject(input.gui) ? input.gui : {};
  const outputs = isObject(input.outputs) ? input.outputs : {};
  const approval = isObject(input.approval) ? input.approval : {};
  const course = isObject(input.course) ? input.course : {};
  const errors = Array.isArray(input.errors) ? input.errors : [];
  const fallbackCourse =
    typeof state === "undefined" ? emptyCourse : selectedCourse();
  const validationMessages = [];

  if (input.schemaVersion !== "1.0.0") {
    validationMessages.push("schemaVersionがMVPの1.0.0ではありません。");
  }

  if (!isObject(input.summary)) {
    validationMessages.push("summaryが不足しています。");
  }

  return {
    schemaVersion: input.schemaVersion ?? "unknown",
    requestId: input.requestId ?? "",
    generatedAt: input.generatedAt ?? "",
    agentTaskType: input.agentTaskType ?? "ERROR_ANALYSIS",
    status: input.status ?? "error",
    course: {
      courseId: course.courseId ?? fallbackCourse.courseId,
      name: course.name ?? fallbackCourse.name,
      section: course.section ?? fallbackCourse.section,
    },
    summary: {
      title: summary.title ?? "処理結果",
      shortSummary: summary.shortSummary ?? "表示できる要約がありません。",
      teacherActionRequired: Boolean(summary.teacherActionRequired),
      recommendedAction: summary.recommendedAction ?? "再試行してください。",
    },
    gui: {
      cards: Array.isArray(gui.cards) ? gui.cards : [],
      tables: Array.isArray(gui.tables) ? gui.tables : [],
      warnings: Array.isArray(gui.warnings) ? gui.warnings : [],
      editableFields: Array.isArray(gui.editableFields) ? gui.editableFields : [],
    },
    outputs: {
      markdown: outputs.markdown ?? null,
      pdf: outputs.pdf ?? null,
      googleDocument: outputs.googleDocument ?? null,
      classroomReminder: outputs.classroomReminder ?? null,
    },
    approval: {
      required: Boolean(approval.required),
      reason: approval.reason ?? "",
      actions: Array.isArray(approval.actions) ? approval.actions : [],
    },
    errors,
    validationMessages,
    raw: input,
  };
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function selectedCourse() {
  return (
    state.courses.find((course) => course.courseId === state.selectedCourseId) ??
    state.courses[0] ??
    emptyCourse
  );
}

function selectedAssignment() {
  return (
    state.assignments.find(
      (assignment) => assignment.courseWorkId === state.selectedAssignmentId,
    ) ??
    state.assignments[0] ??
    emptyAssignment
  );
}

function resetEditableValues() {
  state.editableValues = Object.fromEntries(
    state.agentOutput.gui.editableFields.map((field) => [
      field.fieldId,
      field.value ?? "",
    ]),
  );
  state.fieldErrors = {};
  state.posted = false;
  state.postMessage = "";
  state.postMessageTone = "success";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatGeneratedAt(value) {
  return value ? value.replace("T", " ").replace("+09:00", "") : "未生成";
}

function statusLabel(status) {
  const labels = {
    success: "正常",
    partial_success: "部分成功",
    error: "失敗",
  };
  return labels[status] ?? "不明";
}

function statusBadgeClass(status) {
  if (status === "success") return "success";
  if (status === "partial_success") return "warning";
  return "danger";
}

function pageTitle() {
  const titles = {
    courses: "コース選択",
    dashboard: "ダッシュボード",
    assignment: "課題詳細",
    review: "AI出力確認",
    exports: "出力選択",
    confirm: "投稿確認",
  };
  return titles[state.view] ?? "コース選択";
}

function setLoading(message) {
  state.scenario = scenarioModes.loading;
  state.loadingMessage = message;
  render();
}

function clearLoading() {
  state.loadingMessage = "";
}

function setEmptyState({
  title,
  shortSummary,
  recommendedAction,
  view,
  agentTaskType = "SUBMISSION_ANALYSIS",
}) {
  state.scenario = scenarioModes.empty;
  state.loadingMessage = "";
  state.view = view;
  state.agentOutput = normalizeAgentOutput(
    buildPlaceholderOutput({
      title,
      shortSummary,
      recommendedAction,
      agentTaskType,
    }),
  );
  resetEditableValues();
}

function applyAgentOutput(payload, { view } = {}) {
  state.agentOutput = normalizeAgentOutput(payload);
  state.scenario =
    state.agentOutput.status === "error"
      ? scenarioModes.error
      : scenarioModes.ready;
  state.loadingMessage = "";
  if (view) {
    state.view = view;
  }
  resetEditableValues();
}

function extractApiError(error) {
  const payload = error?.payload;
  if (payload?.error?.message) {
    return {
      code: payload.error.code ?? "CLASSROOM_API_PERMISSION_DENIED",
      message: payload.error.message,
    };
  }
  if (payload?.summary?.shortSummary) {
    const firstError = Array.isArray(payload.errors) ? payload.errors[0] : null;
    return {
      code: firstError?.code ?? "CLASSROOM_API_PERMISSION_DENIED",
      message: firstError?.message ?? payload.summary.shortSummary,
    };
  }
  return {
    code: "CLASSROOM_API_PERMISSION_DENIED",
    message: error?.message ?? "不明なエラーが発生しました。",
  };
}

function handleRequestFailure(error, options) {
  const apiError = extractApiError(error);
  state.loadingMessage = "";
  state.scenario = scenarioModes.error;
  state.view = options.view ?? state.view;
  state.agentOutput = normalizeAgentOutput(
    buildLocalErrorOutput({
      title: options.title,
      shortSummary: options.shortSummary ?? apiError.message,
      recommendedAction: options.recommendedAction,
      errorCode: apiError.code,
      errorMessage: apiError.message,
      agentTaskType: options.agentTaskType,
    }),
  );
  if (options.loggedOut) {
    state.isLoggedIn = false;
  }
  resetEditableValues();
  render();
}

function buildEditedReminderPayload() {
  const reminder = state.agentOutput.outputs.classroomReminder;
  if (!reminder) {
    return null;
  }
  return {
    ...reminder,
    title: state.editableValues.reminder_title ?? reminder.title ?? "",
    text: state.editableValues.reminder_body ?? reminder.text ?? "",
  };
}

function deriveAssignmentMetrics(agentOutput) {
  const table = agentOutput.gui.tables[0];
  const totalRows = Array.isArray(table?.rows) ? table.rows.length : 0;
  const missing = cardNumber(agentOutput.gui.cards, "未提出者数");
  const late = cardNumber(agentOutput.gui.cards, "遅延提出者数");
  return {
    turnedIn: String(Math.max(totalRows - missing, 0)),
    missing: String(missing),
    late: String(late),
  };
}

function cardNumber(cards, title) {
  const card = cards.find((item) => item.title === title);
  const parsed = Number.parseInt(card?.value ?? "0", 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizedAssignments(items) {
  return Array.isArray(items)
    ? items.map((item) => ({
        ...emptyAssignment,
        ...item,
      }))
    : [];
}

function assignmentDisplay(item) {
  const metrics = state.assignmentMetrics[item.courseWorkId];
  return {
    turnedIn: metrics?.turnedIn ?? "未分析",
    missing: metrics?.missing ?? "未分析",
    late: metrics?.late ?? "未分析",
  };
}

function dueDateDistanceCount() {
  return state.assignments.filter((assignment) => {
    if (!assignment.dueDate) return false;
    const due = new Date(`${assignment.dueDate}T${assignment.dueTime ?? "23:59"}:00+09:00`);
    const diffMs = due.getTime() - Date.now();
    return diffMs >= 0 && diffMs <= 3 * 24 * 60 * 60 * 1000;
  }).length;
}

function render() {
  app.innerHTML = `${state.isLoggedIn ? renderShell() : renderLogin()}${renderOAuthDialog()}`;
  bindEvents();
}

function renderLogin() {
  return `
    <main class="login">
      <section class="login-panel">
        <p class="login-kicker">Google Classroom operations</p>
        <h1>Classroom運用支援</h1>
        <p class="subtle">Google Classroomの提出状況を確認し、AIの提案を教師が編集・承認してから投稿します。</p>
        <ul class="check-list">
          <li>読み取り権限と投稿権限を分けて扱う</li>
          <li>生徒向け投稿には未提出者名を含めない</li>
          <li>Classroom投稿は承認画面を必ず通す</li>
        </ul>
        ${
          state.scenario === scenarioModes.error
            ? renderAlert("danger", state.agentOutput.summary.shortSummary)
            : ""
        }
        ${
          state.scenario === scenarioModes.loading
            ? `<p class="subtle">${escapeHtml(
                state.loadingMessage || "保存済みセッションを確認しています。",
              )}</p>`
            : ""
        }
        <button class="button primary" data-action="login">Google Classroomに接続</button>
      </section>
    </main>
  `;
}

function renderOAuthDialog() {
  if (!state.oauthDialog.open) {
    return "";
  }

  const copy = oauthIntentCopy(state.oauthDialog.intent);
  return `
    <div class="modal-backdrop" role="presentation">
      <section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="oauth_dialog_title">
        <div class="card-header">
          <div>
            <p class="login-kicker">Google Classroom OAuth</p>
            <h2 id="oauth_dialog_title">${escapeHtml(copy.title)}</h2>
          </div>
          <button class="button ghost compact" data-action="oauth-close">閉じる</button>
        </div>
        <p class="subtle">${escapeHtml(copy.description)}</p>
        <div class="warning-list">
          <div class="warning-item">
            Google の認可画面は別ウィンドウで開きます。許可後はこの画面に戻ってください。
          </div>
          ${
            state.oauthDialog.errorMessage
              ? `<div class="error-item"><strong>OAuth</strong><span>${escapeHtml(state.oauthDialog.errorMessage)}</span></div>`
              : ""
          }
        </div>
        <div class="action-row" style="margin-top: 18px;">
          <button class="button primary" data-action="oauth-open">認可画面を開く</button>
          <a class="button" href="${escapeHtml(state.oauthDialog.authorizationUrl)}" target="_blank" rel="noopener noreferrer">別タブで開く</a>
        </div>
        <p class="subtle" style="margin: 14px 0 0;">
          画面が開かない場合は、ブラウザのポップアップブロック設定を確認してください。
        </p>
      </section>
    </div>
  `;
}

function renderShell() {
  const course = selectedCourse();
  return `
    <div class="layout">
      <aside class="sidebar">
        <div class="brand">
          <span class="brand-mark">C</span>
          <span>Classroom支援</span>
        </div>
        <div class="sidebar-context">
          <strong>${escapeHtml(course.name)}</strong>
          <span class="subtle">${escapeHtml(course.section)} / ${course.studentCount}名</span>
        </div>
        <nav class="nav" aria-label="主画面">
          ${navButton("courses", "01", "コース選択")}
          ${navButton("dashboard", "02", "ダッシュボード")}
          ${navButton("assignment", "03", "課題詳細")}
          ${navButton("review", "04", "出力確認")}
          ${navButton("exports", "05", "出力選択")}
          ${navButton("confirm", "06", "投稿確認")}
        </nav>
      </aside>
      <main class="main">
        <header class="topbar">
          <div>
            <h1>${pageTitle()}</h1>
            <div class="meta-row">
              <span class="badge">${escapeHtml(course.name)} / ${escapeHtml(course.section)}</span>
              <span class="subtle">生成 ${formatGeneratedAt(state.agentOutput.generatedAt)}</span>
              <span class="badge ${statusBadgeClass(state.agentOutput.status)}">${statusLabel(state.agentOutput.status)}</span>
            </div>
          </div>
          <div class="action-row">
            <button class="button ghost" data-action="retry">再取得</button>
            <button class="button" data-action="logout">ログアウト</button>
          </div>
        </header>
        <div class="content" aria-live="polite">
          ${renderToolbar()}
          ${renderStatusBanner()}
          ${renderView()}
        </div>
      </main>
    </div>
  `;
}

function navButton(view, icon, label) {
  const active = state.view === view ? " active" : "";
  const current = state.view === view ? ' aria-current="page"' : "";
  return `<button class="nav-button${active}" data-view="${view}"${current}><span>${icon}</span><span>${label}</span></button>`;
}

function renderToolbar() {
  return `
    <section class="toolbar" aria-label="データ状態">
      ${renderWorkflow()}
      <div class="approval-meta">
        <span class="badge success">ライブデータ</span>
        <span class="subtle">${escapeHtml(state.loadingMessage || "server-side OAuth / Google Classroom API")}</span>
      </div>
    </section>
  `;
}

function renderWorkflow() {
  const currentIndex = workflowSteps.findIndex(([view]) => view === state.view);
  return `
    <div class="workflow" aria-label="業務フロー">
      ${workflowSteps
        .map(([view, label], index) => {
          const active = view === state.view || (view === "login" && !state.isLoggedIn);
          const done = state.isLoggedIn && index < currentIndex;
          const className = `workflow-step${active ? " active" : ""}${done ? " done" : ""}`;
          return `<span class="${className}">${index + 1}. ${label}</span>`;
        })
        .join("")}
    </div>
  `;
}

function renderStatusBanner() {
  if (state.scenario === scenarioModes.loading) {
    return `
      <section class="state-panel loading-panel" role="status">
        <span class="spinner" aria-hidden="true"></span>
        <div>
          <h2>データ取得中</h2>
          <p class="subtle">${escapeHtml(state.loadingMessage || "Google Classroom情報を読み込んでいます。")}</p>
        </div>
      </section>
    `;
  }

  if (state.agentOutput.status === "partial_success") {
    return renderAlert("warning", state.agentOutput.summary.shortSummary);
  }

  if (state.agentOutput.status === "error" || state.scenario === scenarioModes.error) {
    return renderAlert("danger", state.agentOutput.summary.shortSummary);
  }

  if (state.agentOutput.validationMessages.length > 0) {
    return renderAlert("warning", state.agentOutput.validationMessages.join(" "));
  }

  return "";
}

function renderAlert(level, message) {
  return `
    <section class="alert ${level}" role="alert">
      <strong>${level === "danger" ? "エラー" : "注意"}</strong>
      <span>${escapeHtml(message)}</span>
    </section>
  `;
}

function renderView() {
  if (state.scenario === scenarioModes.loading) {
    return renderLoadingSkeleton();
  }

  if (state.scenario === scenarioModes.empty) {
    return renderEmptyState();
  }

  if (state.scenario === scenarioModes.error && state.view !== "courses") {
    return renderErrorState();
  }

  const views = {
    courses: renderCourses,
    dashboard: renderDashboard,
    assignment: renderAssignment,
    review: renderReview,
    exports: renderExports,
    confirm: renderConfirm,
  };
  return (views[state.view] ?? renderCourses)();
}

function renderLoadingSkeleton() {
  return `
    <section class="grid cols-3" aria-hidden="true">
      ${["", "", ""].map(() => '<div class="skeleton card"></div>').join("")}
    </section>
    <section class="skeleton table-skeleton" aria-hidden="true"></section>
  `;
}

function renderEmptyState() {
  return `
    <section class="empty-state">
      <h2>${escapeHtml(state.agentOutput.summary.title)}</h2>
      <p class="subtle">${escapeHtml(state.agentOutput.summary.shortSummary)}</p>
      <p class="subtle">${escapeHtml(state.agentOutput.summary.recommendedAction)}</p>
      <button class="button primary" data-action="retry">再試行</button>
    </section>
  `;
}

function renderErrorState() {
  return `
    <section class="empty-state error-state">
      <h2>${escapeHtml(state.agentOutput.summary.title)}</h2>
      <p class="subtle">${escapeHtml(state.agentOutput.summary.recommendedAction)}</p>
      ${renderErrors()}
      <button class="button primary" data-action="retry">再試行</button>
    </section>
  `;
}

function renderCourses() {
  return `
    <section class="band">
      <div class="section-heading">
        <div>
          <h2>担当コース</h2>
          <p class="subtle">OAuthで許可されたGoogle Classroomコースを取得し、提出状況の分析対象を選びます。</p>
        </div>
        <span class="badge success">Google Classroom</span>
      </div>
      ${
        state.courses.length === 0
          ? renderInlineEmpty("表示できるコースがありません。Google Classroom の権限とコース状態を確認してください。")
          : `<div class="grid cols-2">
              ${state.courses
                .map(
                  (course) => `
                    <article class="card ${course.courseId === state.selectedCourseId ? "selected" : ""}">
                      <div class="card-header">
                        <h3>${escapeHtml(course.name)}</h3>
                        ${course.courseId === state.selectedCourseId ? '<span class="badge success">選択中</span>' : ""}
                      </div>
                      <p class="subtle">${escapeHtml(course.section)} / ${course.studentCount}名 / 状態 ${escapeHtml(course.state ?? "UNKNOWN")}</p>
                      <div class="action-row" style="margin-top: 16px">
                        <button class="button primary" data-course="${course.courseId}">このコースを開く</button>
                      </div>
                    </article>
                  `,
                )
                .join("")}
            </div>`
      }
    </section>
  `;
}

function renderDashboard() {
  const assignment = selectedAssignment();
  const metrics = state.assignmentMetrics[assignment.courseWorkId] ?? {
    turnedIn: "未分析",
    missing: "未分析",
    late: "未分析",
  };
  return `
    <section class="band">
      <div class="grid cols-3">
        ${metricCard("対象課題", String(state.assignments.length), "公開済み課題の件数", "success")}
        ${metricCard("未提出者", metrics.missing, `${escapeHtml(assignment.title)} の未提出者数`, metrics.missing === "0" ? "success" : "danger")}
        ${metricCard("期限接近課題", String(dueDateDistanceCount()), "3日以内に締切が来る課題数", "warning")}
      </div>
    </section>
    <section class="band">
      <div class="section-heading">
        <div>
          <h2>最近の課題</h2>
          <p class="subtle">Google Classroomから取得した事実データをもとに、対応対象を確認します。</p>
        </div>
        <button class="button" data-view="assignment">課題詳細へ</button>
      </div>
      ${state.assignments.length > 0 ? renderAssignmentTable(state.assignments.slice(0, 5)) : renderInlineEmpty("表示できる課題がありません。")}
    </section>
    <section class="card">
      <div class="card-header">
        <h3>現在の分析要約</h3>
        <span class="badge warning">事実ベース</span>
      </div>
      <p>${escapeHtml(state.agentOutput.summary.shortSummary)}</p>
      <p class="subtle">${escapeHtml(state.agentOutput.summary.recommendedAction)}</p>
    </section>
  `;
}

function metricCard(title, value, description, tone = "") {
  return `
    <article class="card metric ${tone}">
      <h3>${escapeHtml(title)}</h3>
      <div class="metric-value">${escapeHtml(value)}</div>
      <p class="subtle">${escapeHtml(description)}</p>
    </article>
  `;
}

function renderAssignment() {
  const firstTable = state.agentOutput.gui.tables[0];
  return `
    <section class="band">
      <div class="section-heading">
        <div>
          <h2>課題一覧</h2>
          <p class="subtle">課題を選ぶと提出分析を再取得し、必要ならリマインド案を生成します。</p>
        </div>
        <button class="button primary" data-action="generate-reminder" ${state.selectedAssignmentId ? "" : "disabled"}>リマインド文を生成</button>
      </div>
      ${state.assignments.length > 0 ? renderAssignmentTable(state.assignments) : renderInlineEmpty("表示できる課題がありません。")}
    </section>
    <section class="band">
      <div class="section-heading">
        <h2>提出状況</h2>
        <span class="badge warning">選択中の課題</span>
      </div>
      ${firstTable ? renderAgentTable(firstTable) : renderInlineEmpty("提出状況は未取得です。")}
    </section>
  `;
}

function renderAssignmentTable(items) {
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>課題</th>
            <th>締切</th>
            <th>提出済み</th>
            <th>未提出</th>
            <th>遅延</th>
            <th>状態</th>
          </tr>
        </thead>
        <tbody>
          ${items
            .map((item) => {
              const display = assignmentDisplay(item);
              return `
                <tr class="${item.courseWorkId === state.selectedAssignmentId ? "selected-row" : ""}">
                  <td>${escapeHtml(item.title)}</td>
                  <td>${escapeHtml(item.dueDate ?? "未設定")} ${escapeHtml(item.dueTime ?? "")}</td>
                  <td><span class="badge success">${escapeHtml(display.turnedIn)}</span></td>
                  <td><span class="badge danger">${escapeHtml(display.missing)}</span></td>
                  <td><span class="badge warning">${escapeHtml(display.late)}</span></td>
                  <td>
                    <span class="badge">${escapeHtml(item.state ?? "UNKNOWN")}</span>
                    <button class="button ghost compact" data-assignment="${item.courseWorkId}">選択</button>
                  </td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderReview() {
  const output = state.agentOutput;
  return `
    <section class="band">
      <div class="section-heading">
        <h2>${escapeHtml(output.summary.title)}</h2>
        <span class="badge">${escapeHtml(output.schemaVersion)}</span>
      </div>
      ${
        output.gui.cards.length > 0
          ? `<div class="grid cols-3">${output.gui.cards
              .map((card, index) =>
                metricCard(
                  card.title,
                  card.value,
                  card.description,
                  ["danger", "warning", "success"][index] ?? "",
                ),
              )
              .join("")}</div>`
          : renderInlineEmpty("カード表示用データはありません。")
      }
    </section>
    <section class="review-layout">
      <div class="card">
        <div class="card-header">
          <h3>編集</h3>
          <span class="badge">教師確認</span>
        </div>
        <div class="grid" style="margin-top: 14px">
          ${
            output.gui.editableFields.length > 0
              ? output.gui.editableFields.map(renderEditableField).join("")
              : renderInlineEmpty("編集可能な項目はありません。")
          }
        </div>
      </div>
      <div class="card">
        <div class="card-header">
          <h3>警告とエラー</h3>
          <span class="badge warning">投稿前確認</span>
        </div>
        <div class="warning-list" style="margin-top: 14px">
          ${renderWarnings()}
          ${renderErrors()}
        </div>
      </div>
    </section>
    <section class="split">
      <div class="card">
        <h3>契約チェック</h3>
        ${renderContractChecklist()}
      </div>
      <div class="card">
        <h3>承認アクション</h3>
        ${renderApprovalActions()}
      </div>
    </section>
    <section class="band">
      ${
        output.gui.tables.length > 0
          ? output.gui.tables.map(renderAgentTableSection).join("")
          : renderInlineEmpty("表形式のデータはありません。")
      }
    </section>
    ${renderDeveloperPanel()}
  `;
}

function renderContractChecklist() {
  const checks = [
    ["schemaVersion", state.agentOutput.schemaVersion === "1.0.0"],
    ["summary", Boolean(state.agentOutput.summary.title)],
    ["gui.cards", Array.isArray(state.agentOutput.gui.cards)],
    ["gui.tables", Array.isArray(state.agentOutput.gui.tables)],
    ["gui.warnings", Array.isArray(state.agentOutput.gui.warnings)],
    ["gui.editableFields", Array.isArray(state.agentOutput.gui.editableFields)],
    ["outputs.markdown", "markdown" in state.agentOutput.outputs],
    ["outputs.pdf", "pdf" in state.agentOutput.outputs],
    ["outputs.googleDocument", "googleDocument" in state.agentOutput.outputs],
    ["outputs.classroomReminder", "classroomReminder" in state.agentOutput.outputs],
    ["approval.actions", Array.isArray(state.agentOutput.approval.actions)],
    ["errors", Array.isArray(state.agentOutput.errors)],
  ];
  return `
    <ul class="contract-list">
      ${checks
        .map(
          ([label, passed]) => `
            <li class="${passed ? "passed" : "failed"}">
              <span aria-hidden="true">${passed ? "✓" : "!"}</span>
              <span>${escapeHtml(label)}</span>
            </li>
          `,
        )
        .join("")}
    </ul>
  `;
}

function renderApprovalActions() {
  if (state.agentOutput.approval.actions.length === 0) {
    return renderInlineEmpty("承認対象のアクションはありません。");
  }
  return `
    <div class="approval-list">
      ${state.agentOutput.approval.actions
        .map(
          (action) => `
            <article class="approval-action">
              <div>
                <h4>${escapeHtml(action.label ?? action.type ?? "承認アクション")}</h4>
                <p class="subtle">${escapeHtml(action.type ?? "")}</p>
              </div>
              <div class="approval-meta">
                ${action.requiresConfirmation ? '<span class="badge danger">確認必須</span>' : '<span class="badge">確認不要</span>'}
                <span class="badge">${escapeHtml(action.payloadRef ?? "payload未指定")}</span>
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderDeveloperPanel() {
  return `
    <section class="card developer-panel">
      <div class="section-heading">
        <h2>開発者モード</h2>
        <button class="button" data-action="toggle-developer">${state.developerMode ? "閉じる" : "開く"}</button>
      </div>
      ${
        state.developerMode
          ? `<div class="developer-grid">
              <div>
                <h3>Raw JSON</h3>
                <pre class="json-preview">${escapeHtml(JSON.stringify(state.agentOutput.raw, null, 2))}</pre>
              </div>
              <div>
                <h3>Normalized JSON</h3>
                <pre class="json-preview">${escapeHtml(JSON.stringify({ ...state.agentOutput, raw: undefined }, null, 2))}</pre>
              </div>
            </div>`
          : '<p class="subtle">AIアウトプットJSONは開発者モードでのみ直接表示します。</p>'
      }
    </section>
  `;
}

function renderWarnings() {
  if (state.agentOutput.gui.warnings.length === 0) {
    return renderInlineEmpty("警告はありません。");
  }
  return state.agentOutput.gui.warnings
    .map(
      (warning) =>
        `<div class="warning-item ${warning.level === "high" ? "high" : ""}">${escapeHtml(warning.message)}</div>`,
    )
    .join("");
}

function renderErrors() {
  if (state.agentOutput.errors.length === 0) {
    return "";
  }
  return state.agentOutput.errors
    .map(
      (error) => `
        <div class="error-item">
          <strong>${escapeHtml(error.code ?? "UNKNOWN_ERROR")}</strong>
          <span>${escapeHtml(error.message ?? "不明なエラーです。")}</span>
          ${error.recoverable ? '<span class="badge warning">再試行可</span>' : ""}
        </div>
      `,
    )
    .join("");
}

function renderEditableField(field) {
  const value = state.editableValues[field.fieldId] ?? "";
  const error = state.fieldErrors[field.fieldId] ?? "";
  const required = field.required ? "required" : "";
  const invalid = error ? 'aria-invalid="true"' : "";
  const describedBy = error ? `aria-describedby="${field.fieldId}_error"` : "";
  if (field.type === "textarea") {
    return `
      <div class="field">
        <label for="${field.fieldId}">${escapeHtml(field.label)}</label>
        <textarea id="${field.fieldId}" data-field="${field.fieldId}" ${required} ${invalid} ${describedBy}>${escapeHtml(value)}</textarea>
        ${error ? `<p class="field-error" id="${field.fieldId}_error">${escapeHtml(error)}</p>` : ""}
      </div>
    `;
  }
  return `
    <div class="field">
      <label for="${field.fieldId}">${escapeHtml(field.label)}</label>
      <input id="${field.fieldId}" data-field="${field.fieldId}" value="${escapeHtml(value)}" ${required} ${invalid} ${describedBy} />
      ${error ? `<p class="field-error" id="${field.fieldId}_error">${escapeHtml(error)}</p>` : ""}
    </div>
  `;
}

function renderAgentTableSection(table) {
  return `
    <div class="section-heading">
      <h2>${escapeHtml(table.title)}</h2>
    </div>
    ${renderAgentTable(table)}
  `;
}

function renderAgentTable(table) {
  if (!table || !Array.isArray(table.columns) || table.columns.length === 0) {
    return renderInlineEmpty("列定義がありません。");
  }
  if (!Array.isArray(table.rows) || table.rows.length === 0) {
    return renderInlineEmpty("行データがありません。");
  }
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>${table.columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${table.rows
            .map(
              (row) => `
                <tr>
                  ${table.columns
                    .map((column) => `<td>${escapeHtml(row[column.key] ?? "")}</td>`)
                    .join("")}
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderInlineEmpty(message) {
  return `<p class="inline-empty">${escapeHtml(message)}</p>`;
}

function renderExports() {
  const options = [
    ["classroom", "Classroomリマインド", "承認後にお知らせとして投稿", Boolean(state.agentOutput.outputs.classroomReminder)],
    ["markdown", "Markdown", "議事録や共有用に保存", Boolean(state.agentOutput.outputs.markdown)],
    ["pdf", "PDF", "会議資料や記録用に出力", Boolean(state.agentOutput.outputs.pdf)],
  ];
  return `
    <section class="band">
      <div class="section-heading">
        <h2>出力形式</h2>
        <button class="button primary" data-view="confirm" ${state.selectedOutputs.size === 0 ? "disabled" : ""}>確認へ進む</button>
      </div>
      <div class="grid cols-3">
        ${options
          .map(
            ([key, title, description, available]) => `
              <label class="card output-option ${available ? "" : "disabled"}">
                <div class="card-header">
                  <input type="checkbox" data-output="${key}" ${state.selectedOutputs.has(key) ? "checked" : ""} ${available ? "" : "disabled"} />
                  <span class="badge ${available ? "success" : "warning"}">${available ? "利用可" : "未生成"}</span>
                </div>
                <h3 style="margin-top: 12px">${title}</h3>
                <p class="subtle">${description}</p>
              </label>
            `,
          )
          .join("")}
      </div>
    </section>
    <section class="card">
      <h3>Markdownプレビュー</h3>
      ${
        state.agentOutput.outputs.markdown
          ? `<pre class="output-preview">${escapeHtml(state.agentOutput.outputs.markdown.content)}</pre>`
          : renderInlineEmpty("Markdown出力はありません。")
      }
    </section>
  `;
}

function renderConfirm() {
  const reminder = buildEditedReminderPayload();
  const title = reminder?.title ?? "";
  const body = reminder?.text ?? "";
  const canPost = Boolean(reminder) && validateEditableFields(false);
  return `
    <section class="band">
      <div class="section-heading">
        <h2>Classroom投稿前確認</h2>
        <span class="badge danger">教師承認が必要</span>
      </div>
      <div class="grid cols-2">
        <article class="card">
          <h3>投稿先</h3>
          <p>${escapeHtml(selectedCourse().name)} / ${escapeHtml(selectedCourse().section)}</p>
          <p class="subtle">課題: ${escapeHtml(selectedAssignment().title)}</p>
        </article>
        <article class="card">
          <h3>公開範囲</h3>
          <p>${escapeHtml(reminder?.assigneeMode === "INDIVIDUAL_STUDENTS" ? "個別配信" : "コース全体")}</p>
          <p class="subtle">個別生徒名は投稿本文に含めない設定です。</p>
        </article>
      </div>
    </section>
    <section class="card">
      <div class="card-header">
        <h3>${escapeHtml(title || "投稿タイトル未入力")}</h3>
        <span class="badge danger">未承認</span>
      </div>
      <p>${escapeHtml(body || "投稿本文未入力")}</p>
    </section>
    <section class="approval-summary">
      <strong>承認条件</strong>
      <span>${escapeHtml(state.agentOutput.approval.reason || "承認対象の操作はありません。")}</span>
      <span class="subtle">教師が内容を確認し、投稿ボタンを押すまで Classroom への投稿は実行されません。</span>
    </section>
    ${
      state.postMessage
        ? renderAlert(state.postMessageTone, state.postMessage)
        : ""
    }
    <section class="action-row">
      <button class="button primary" data-action="approve-post" ${state.posted || !canPost ? "disabled" : ""}>投稿する</button>
      <button class="button" data-view="review">文面を修正</button>
      ${state.posted ? '<span class="badge success">投稿完了</span>' : ""}
      ${!canPost ? '<span class="badge warning">投稿内容を確認してください</span>' : ""}
    </section>
  `;
}

function oauthIntentCopy(intent) {
  if (intent === "post") {
    return {
      title: "Classroom 投稿権限を許可してください",
      description:
        "教師承認後にお知らせを投稿するため、Google Classroom の投稿権限が必要です。",
    };
  }
  return {
    title: "Google Classroom への接続を許可してください",
    description:
      "コース一覧、課題、提出状況を取得するため、Google Classroom の読み取り権限が必要です。",
  };
}

function resetOAuthDialog() {
  state.oauthDialog = { ...emptyOAuthDialog };
}

function openOAuthPopupWindow() {
  const popup = window.open(
    state.oauthDialog.authorizationUrl,
    "sansan-google-oauth",
    "popup=yes,width=560,height=720",
  );
  if (!popup) {
    state.oauthDialog.errorMessage =
      "ポップアップを開けませんでした。下のリンクから別タブで開いてください。";
    render();
    return;
  }
  popup.focus();
}

async function ensureGoogleAuthorization(intent) {
  const payload = await apiFetchJson(
    `/api/live/oauth/start?intent=${encodeURIComponent(intent)}`,
  );
  if (payload.status === "authorized") {
    oauthPollGeneration += 1;
    resetOAuthDialog();
    render();
    return;
  }
  if (payload.status !== "authorization_required") {
    throw new Error("OAuth 開始レスポンスが不正です。");
  }

  const generation = ++oauthPollGeneration;
  state.oauthDialog = {
    open: true,
    intent,
    authorizationUrl: payload.authorizationUrl ?? "",
    statusUrl: payload.statusUrl ?? "",
    errorMessage: "",
  };
  clearLoading();
  render();
  await waitForOAuthCompletion(generation, payload.statusUrl ?? "");
}

async function waitForOAuthCompletion(generation, statusUrl) {
  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    if (generation !== oauthPollGeneration || !state.oauthDialog.open) {
      const cancelled = new Error("OAuth flow was cancelled.");
      cancelled.cancelled = true;
      throw cancelled;
    }

    const payload = await apiFetchJson(statusUrl);
    if (payload.status === "completed" || payload.status === "authorized") {
      resetOAuthDialog();
      render();
      return;
    }
    if (payload.status === "error") {
      state.oauthDialog.errorMessage =
        payload.error?.message ?? "Google OAuth に失敗しました。";
      render();
      throw new Error(state.oauthDialog.errorMessage);
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
  }

  state.oauthDialog.errorMessage =
    "認可の完了を確認できませんでした。認可画面を開き直してください。";
  render();
  throw new Error(state.oauthDialog.errorMessage);
}

function validateEditableFields(updateState = true) {
  const errors = {};
  for (const field of state.agentOutput.gui.editableFields) {
    const value = String(state.editableValues[field.fieldId] ?? "").trim();
    if (field.required && value.length === 0) {
      errors[field.fieldId] = `${field.label}は必須です。`;
    }
  }
  if (updateState) {
    state.fieldErrors = errors;
  }
  return Object.keys(errors).length === 0;
}

async function apiFetchJson(path, options = {}) {
  const headers = {
    Accept: "application/json",
    ...(options.headers ?? {}),
  };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, {
    ...options,
    headers,
  });
  const text = await response.text();
  let payload = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      payload = {};
    }
  }
  if (!response.ok) {
    const message =
      payload?.error?.message ??
      payload?.summary?.shortSummary ??
      `HTTP ${response.status}`;
    const apiError = new Error(message);
    apiError.status = response.status;
    apiError.payload = payload;
    throw apiError;
  }
  return payload;
}

async function loadCoursesAfterAuthorization() {
  setLoading("Google Classroom のコース一覧を取得しています。");
  const payload = await apiFetchJson("/api/live/courses");
  state.courses = Array.isArray(payload.items) ? payload.items : [];
  state.isLoggedIn = true;
  state.view = "courses";
  state.assignmentMetrics = {};
  state.assignments = [];
  state.selectedCourseId = state.courses[0]?.courseId ?? "";
  state.selectedAssignmentId = "";
  window.sessionStorage.removeItem(manualLogoutStorageKey);
  if (state.courses.length === 0) {
    setEmptyState({
      title: "表示できるコースがありません",
      shortSummary: "Google Classroom から対象コースを取得できませんでした。",
      recommendedAction: "コースの教師権限と公開状態を確認してください。",
      view: "courses",
    });
    render();
    return;
  }
  await loadCourseContext(state.selectedCourseId, { nextView: "dashboard" });
}

async function connectGoogle({ skipAuthorizationCheck = false } = {}) {
  if (!skipAuthorizationCheck) {
    try {
      await ensureGoogleAuthorization("read");
    } catch (error) {
      if (error?.cancelled) {
        state.scenario = scenarioModes.ready;
        clearLoading();
        render();
        return;
      }
      handleRequestFailure(error, {
        title: "Google Classroom への接続に失敗しました",
        recommendedAction:
          "OAuth の認可画面を開いて、Google Classroom の読み取り権限を許可してください。",
        loggedOut: true,
        view: "login",
      });
      return;
    }
  }

  try {
    await loadCoursesAfterAuthorization();
  } catch (error) {
    handleRequestFailure(error, {
      title: "コース一覧の取得に失敗しました",
      recommendedAction: "credentials.json、token.json、Google Classroom の権限設定を確認してください。",
      loggedOut: true,
      view: "login",
    });
  }
}

async function bootstrapGoogleSession() {
  if (window.sessionStorage.getItem(manualLogoutStorageKey) === "1") {
    return;
  }

  state.scenario = scenarioModes.loading;
  state.loadingMessage = "保存済みの Google Classroom セッションを確認しています。";
  render();

  try {
    const payload = await apiFetchJson("/api/live/oauth/check?intent=read");
    if (payload.status !== "authorized") {
      state.scenario = scenarioModes.ready;
      clearLoading();
      render();
      return;
    }
    await connectGoogle({ skipAuthorizationCheck: true });
  } catch (_error) {
    state.scenario = scenarioModes.ready;
    clearLoading();
    render();
  }
}

async function loadCourseContext(courseId, { nextView = "dashboard" } = {}) {
  if (!courseId) {
    setEmptyState({
      title: "コースが選択されていません",
      shortSummary: "分析対象のコースを選択してください。",
      recommendedAction: "コース一覧から対象コースを選び直してください。",
      view: "courses",
    });
    render();
    return;
  }

  state.selectedCourseId = courseId;
  state.assignments = [];
  state.assignmentMetrics = {};
  state.selectedAssignmentId = "";
  setLoading("課題一覧を取得しています。");
  try {
    const payload = await apiFetchJson(
      `/api/live/coursework?courseId=${encodeURIComponent(courseId)}`,
    );
    state.assignments = normalizedAssignments(payload.items);
    state.selectedAssignmentId = state.assignments[0]?.courseWorkId ?? "";
    if (state.assignments.length === 0) {
      setEmptyState({
        title: "公開済み課題がありません",
        shortSummary: "このコースには取得対象の課題がありません。",
        recommendedAction: "PUBLISHED 状態の課題を確認するか、別のコースを選択してください。",
        view: "assignment",
      });
      render();
      return;
    }
    await loadSubmissionAnalysis(courseId, state.selectedAssignmentId, {
      nextView,
    });
  } catch (error) {
    handleRequestFailure(error, {
      title: "課題一覧の取得に失敗しました",
      recommendedAction: "Classroom の課題権限と対象コースIDを確認してください。",
      view: "courses",
    });
  }
}

async function loadSubmissionAnalysis(
  courseId,
  courseWorkId,
  { nextView = "assignment" } = {},
) {
  if (!courseId || !courseWorkId) {
    setEmptyState({
      title: "課題が選択されていません",
      shortSummary: "提出状況を分析する課題を選択してください。",
      recommendedAction: "課題一覧から対象課題を選び直してください。",
      view: "assignment",
    });
    render();
    return;
  }

  state.selectedCourseId = courseId;
  state.selectedAssignmentId = courseWorkId;
  setLoading("提出状況を取得して分析しています。");
  try {
    const payload = await apiFetchJson(
      `/api/live/submission-analysis?courseId=${encodeURIComponent(courseId)}&courseWorkId=${encodeURIComponent(courseWorkId)}`,
    );
    applyAgentOutput(payload, { view: nextView });
    if (state.agentOutput.status !== "error") {
      state.assignmentMetrics[courseWorkId] = deriveAssignmentMetrics(
        state.agentOutput,
      );
    }
    render();
  } catch (error) {
    handleRequestFailure(error, {
      title: "提出状況の取得に失敗しました",
      recommendedAction: "Google Classroom の提出状況取得権限を確認してください。",
      view: "assignment",
    });
  }
}

async function loadReminderGeneration(
  courseId,
  courseWorkId,
  { nextView = "review" } = {},
) {
  if (!courseId || !courseWorkId) {
    setEmptyState({
      title: "課題が選択されていません",
      shortSummary: "リマインド案を生成する課題を選択してください。",
      recommendedAction: "課題一覧から対象課題を選び直してください。",
      view: "assignment",
      agentTaskType: "REMINDER_GENERATION",
    });
    render();
    return;
  }

  setLoading("リマインド案を生成しています。");
  try {
    const payload = await apiFetchJson(
      `/api/live/reminder-generation?courseId=${encodeURIComponent(courseId)}&courseWorkId=${encodeURIComponent(courseWorkId)}`,
    );
    applyAgentOutput(payload, { view: nextView });
    render();
  } catch (error) {
    handleRequestFailure(error, {
      title: "リマインド案の生成に失敗しました",
      recommendedAction: "提出状況を再取得したうえで、もう一度実行してください。",
      view: "review",
      agentTaskType: "REMINDER_GENERATION",
    });
  }
}

async function retryCurrentView() {
  if (!state.isLoggedIn) {
    await connectGoogle();
    return;
  }
  if (!state.selectedCourseId) {
    await connectGoogle();
    return;
  }
  if (state.view === "courses") {
    await loadCourseContext(state.selectedCourseId, { nextView: "dashboard" });
    return;
  }
  if (!state.selectedAssignmentId) {
    await loadCourseContext(state.selectedCourseId, { nextView: "assignment" });
    return;
  }
  if (state.agentOutput.agentTaskType === "REMINDER_GENERATION") {
    await loadReminderGeneration(state.selectedCourseId, state.selectedAssignmentId, {
      nextView: state.view === "confirm" ? "confirm" : "review",
    });
    return;
  }
  await loadSubmissionAnalysis(state.selectedCourseId, state.selectedAssignmentId, {
    nextView: state.view === "courses" ? "dashboard" : state.view,
  });
}

async function postReminder() {
  if (!validateEditableFields(true)) {
    state.view = "review";
    render();
    return;
  }
  const reminder = buildEditedReminderPayload();
  if (!reminder) {
    state.postMessage = "投稿対象の reminder payload がありません。";
    state.postMessageTone = "danger";
    render();
    return;
  }

  try {
    await ensureGoogleAuthorization("post");
  } catch (error) {
    if (error?.cancelled) {
      state.scenario = scenarioModes.ready;
      clearLoading();
      render();
      return;
    }
    const message =
      error?.message ??
      "Google Classroom の投稿権限を許可したうえで再試行してください。";
    state.scenario = scenarioModes.ready;
    clearLoading();
    state.posted = false;
    state.postMessage = message;
    state.postMessageTone = "danger";
    render();
    return;
  }

  setLoading("Classroom に投稿しています。");
  try {
    const payload = await apiFetchJson("/api/live/post-reminder", {
      method: "POST",
      body: JSON.stringify({
        approved: true,
        classroomReminder: reminder,
      }),
    });
    state.scenario = scenarioModes.ready;
    clearLoading();
    state.posted = true;
    state.postMessage = payload.announcementId
      ? `Classroom に投稿しました。announcementId=${payload.announcementId}`
      : "Classroom に投稿しました。";
    state.postMessageTone = "success";
    render();
  } catch (error) {
    const apiError = extractApiError(error);
    state.scenario = scenarioModes.ready;
    clearLoading();
    state.posted = false;
    state.postMessage = apiError.message;
    state.postMessageTone = "danger";
    render();
  }
}

function bindEvents() {
  document.querySelectorAll("[data-action='login']").forEach((button) => {
    button.addEventListener("click", () => {
      void connectGoogle();
    });
  });

  document.querySelectorAll("[data-action='logout']").forEach((button) => {
    button.addEventListener("click", () => {
      window.sessionStorage.setItem(manualLogoutStorageKey, "1");
      state.isLoggedIn = false;
      state.view = "login";
      state.scenario = scenarioModes.ready;
      state.loadingMessage = "";
      state.courses = [];
      state.assignments = [];
      state.assignmentMetrics = {};
      state.selectedCourseId = "";
      state.selectedAssignmentId = "";
      state.agentOutput = normalizeAgentOutput(buildPlaceholderOutput());
      resetEditableValues();
      render();
    });
  });

  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.view === "confirm" && !validateEditableFields(true)) {
        state.view = "review";
      } else {
        state.view = button.dataset.view;
      }
      render();
    });
  });

  document.querySelectorAll("[data-course]").forEach((button) => {
    button.addEventListener("click", () => {
      void loadCourseContext(button.dataset.course, { nextView: "dashboard" });
    });
  });

  document.querySelectorAll("[data-assignment]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedAssignmentId = button.dataset.assignment;
      void loadSubmissionAnalysis(state.selectedCourseId, button.dataset.assignment, {
        nextView: "assignment",
      });
    });
  });

  document.querySelectorAll("[data-action='generate-reminder']").forEach((button) => {
    button.addEventListener("click", () => {
      void loadReminderGeneration(state.selectedCourseId, state.selectedAssignmentId, {
        nextView: "review",
      });
    });
  });

  document.querySelectorAll("[data-action='retry']").forEach((button) => {
    button.addEventListener("click", () => {
      void retryCurrentView();
    });
  });

  document.querySelectorAll("[data-action='toggle-developer']").forEach((button) => {
    button.addEventListener("click", () => {
      state.developerMode = !state.developerMode;
      render();
    });
  });

  document.querySelectorAll("[data-field]").forEach((field) => {
    field.addEventListener("input", () => {
      state.editableValues[field.dataset.field] = field.value;
      delete state.fieldErrors[field.dataset.field];
      state.posted = false;
      state.postMessage = "";
    });
  });

  document.querySelectorAll("[data-output]").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        state.selectedOutputs.add(checkbox.dataset.output);
      } else {
        state.selectedOutputs.delete(checkbox.dataset.output);
      }
      render();
    });
  });

  document.querySelectorAll("[data-action='approve-post']").forEach((button) => {
    button.addEventListener("click", () => {
      void postReminder();
    });
  });

  document.querySelectorAll("[data-action='oauth-open']").forEach((button) => {
    button.addEventListener("click", () => {
      openOAuthPopupWindow();
    });
  });

  document.querySelectorAll("[data-action='oauth-close']").forEach((button) => {
    button.addEventListener("click", () => {
      oauthPollGeneration += 1;
      resetOAuthDialog();
      state.scenario = scenarioModes.ready;
      clearLoading();
      render();
    });
  });
}
