const rawAgentOutputs = {
  success: {
    schemaVersion: "1.0.0",
    requestId: "req_20260703_001",
    generatedAt: "2026-07-03T13:00:00+09:00",
    agentTaskType: "REMINDER_GENERATION",
    status: "success",
    course: {
      courseId: "123456789",
      name: "数学I",
      section: "1年A組",
    },
    summary: {
      title: "未提出課題リマインド案",
      shortSummary: "数学Iの課題「二次関数プリント」に未提出者が12名います。",
      teacherActionRequired: true,
      recommendedAction:
        "未提出者に対してClassroomでリマインドを投稿してください。",
    },
    gui: {
      cards: [
        {
          cardId: "card_001",
          type: "metric",
          title: "未提出者数",
          value: "12",
          description: "課題「二次関数プリント」の未提出者数です。",
        },
        {
          cardId: "card_002",
          type: "metric",
          title: "期限まで",
          value: "2日",
          description: "締切は2026-07-05 23:59です。",
        },
        {
          cardId: "card_003",
          type: "metric",
          title: "遅延提出",
          value: "3",
          description: "提出済みですが締切後の提出です。",
        },
      ],
      tables: [
        {
          tableId: "table_001",
          title: "未提出者一覧",
          columns: [
            { key: "studentName", label: "生徒名" },
            { key: "status", label: "状態" },
            { key: "dueDate", label: "締切" },
          ],
          rows: [
            { studentName: "山田太郎", status: "未提出", dueDate: "2026-07-05" },
            { studentName: "佐藤花子", status: "未提出", dueDate: "2026-07-05" },
            { studentName: "鈴木一郎", status: "期限接近", dueDate: "2026-07-05" },
          ],
        },
      ],
      warnings: [
        {
          level: "medium",
          message: "生徒向け投稿には、個別の未提出者名を含めないでください。",
        },
        {
          level: "high",
          message: "Classroom投稿は教師の承認後にのみ実行してください。",
        },
      ],
      editableFields: [
        {
          fieldId: "reminder_title",
          label: "投稿タイトル",
          type: "text",
          value: "課題提出リマインド",
          required: true,
        },
        {
          fieldId: "reminder_body",
          label: "リマインド本文",
          type: "textarea",
          value:
            "課題「二次関数プリント」の提出期限が近づいています。まだ提出していない人は、7月5日までに提出してください。分からないところがある場合は、早めに相談してください。",
          required: true,
        },
      ],
    },
    outputs: {
      markdown: {
        fileName: "math1_submission_report_20260703.md",
        title: "数学I 提出状況レポート",
        content:
          "# 数学I 提出状況レポート\n\n## 概要\n課題「二次関数プリント」に未提出者が12名います。\n\n## 推奨アクション\nClassroomで全体向けのリマインドを投稿してください。",
      },
      pdf: {
        fileName: "math1_submission_report_20260703.pdf",
        title: "数学I 提出状況レポート",
        layout: "report",
        sections: [
          {
            heading: "概要",
            body: "数学Iの課題提出状況をまとめたレポートです。",
          },
        ],
      },
      googleDocument: null,
      classroomReminder: {
        target: {
          courseId: "123456789",
          courseWorkId: "987654321",
        },
        postType: "announcement",
        title: "課題提出リマインド",
        text:
          "課題「二次関数プリント」の提出期限が近づいています。まだ提出していない人は、7月5日までに提出してください。",
        materials: [],
        scheduledTime: null,
        assigneeMode: "ALL_STUDENTS",
        targetStudentIds: [],
        requiresTeacherApproval: true,
      },
    },
    approval: {
      required: true,
      reason: "Classroomへの投稿を行うため、教師の承認が必要です。",
      actions: [
        {
          actionId: "action_001",
          type: "CREATE_CLASSROOM_ANNOUNCEMENT",
          label: "Classroomにリマインドを投稿",
          requiresConfirmation: true,
          payloadRef: "outputs.classroomReminder",
        },
        {
          actionId: "action_002",
          type: "EXPORT_MARKDOWN",
          label: "Markdownとして保存",
          requiresConfirmation: false,
          payloadRef: "outputs.markdown",
        },
        {
          actionId: "action_003",
          type: "EXPORT_PDF",
          label: "PDFとして出力",
          requiresConfirmation: false,
          payloadRef: "outputs.pdf",
        },
      ],
    },
    errors: [],
  },
  partial: {
    schemaVersion: "1.0.0",
    requestId: "req_20260703_003",
    generatedAt: "2026-07-03T13:20:00+09:00",
    agentTaskType: "SUBMISSION_ANALYSIS",
    status: "partial_success",
    course: {
      courseId: "123456789",
      name: "数学I",
      section: "1年A組",
    },
    summary: {
      title: "提出状況の部分取得",
      shortSummary: "一部の提出状況だけを取得できました。",
      teacherActionRequired: true,
      recommendedAction: "再試行するか、取得できた範囲で内容を確認してください。",
    },
    gui: {
      cards: [
        {
          cardId: "card_loaded",
          type: "metric",
          title: "取得済み",
          value: "24",
          description: "提出状況を取得できた生徒数です。",
        },
        {
          cardId: "card_failed",
          type: "metric",
          title: "未取得",
          value: "12",
          description: "API制限により取得できなかった生徒数です。",
        },
      ],
      tables: [],
      warnings: [
        {
          level: "high",
          message: "一部データが未取得のため、投稿前に再確認してください。",
        },
      ],
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
      reason: "外部投稿を含まないため承認操作はありません。",
      actions: [],
    },
    errors: [
      {
        code: "CLASSROOM_API_RATE_LIMITED",
        message: "提出状況の一部取得がレート制限で失敗しました。",
        recoverable: true,
      },
    ],
  },
  error: {
    schemaVersion: "1.0.0",
    requestId: "req_20260703_002",
    generatedAt: "2026-07-03T13:10:00+09:00",
    agentTaskType: "SUBMISSION_ANALYSIS",
    status: "error",
    summary: {
      title: "提出状況の取得に失敗しました",
      shortSummary: "Google Classroom APIから提出状況を取得できませんでした。",
      teacherActionRequired: true,
      recommendedAction: "Googleアカウントの権限を確認し、再度実行してください。",
    },
    errors: [
      {
        code: "CLASSROOM_API_PERMISSION_DENIED",
        message: "提出状況を取得する権限がありません。",
        recoverable: true,
      },
    ],
  },
};

const courses = [
  {
    courseId: "123456789",
    name: "数学I",
    section: "1年A組",
    studentCount: 36,
    updatedAt: "2026-07-03 12:20",
  },
  {
    courseId: "223456789",
    name: "情報I",
    section: "1年B組",
    studentCount: 34,
    updatedAt: "2026-07-02 16:40",
  },
];

const assignments = [
  {
    courseWorkId: "987654321",
    title: "二次関数プリント",
    dueDate: "2026-07-05",
    dueTime: "23:59",
    turnedIn: 21,
    missing: 12,
    late: 3,
    state: "PUBLISHED",
  },
  {
    courseWorkId: "887654321",
    title: "小テスト復習",
    dueDate: "2026-07-08",
    dueTime: "18:00",
    turnedIn: 29,
    missing: 7,
    late: 0,
    state: "PUBLISHED",
  },
];

const scenarioModes = {
  ready: "ready",
  loading: "loading",
  empty: "empty",
  partial: "partial",
  error: "error",
};

const state = {
  isLoggedIn: false,
  view: "login",
  selectedCourseId: courses[0].courseId,
  selectedAssignmentId: assignments[0].courseWorkId,
  scenario: "ready",
  agentOutput: normalizeAgentOutput(rawAgentOutputs.success),
  editableValues: {},
  fieldErrors: {},
  selectedOutputs: new Set(["classroom", "markdown"]),
  developerMode: false,
  posted: false,
};

const app = document.querySelector("#app");

const workflowSteps = [
  ["login", "ログイン"],
  ["courses", "コース"],
  ["dashboard", "概要"],
  ["assignment", "課題"],
  ["review", "AI確認"],
  ["exports", "出力"],
  ["confirm", "承認"],
];

resetEditableValues();
render();

function normalizeAgentOutput(payload) {
  const input = isObject(payload) ? payload : {};
  const summary = isObject(input.summary) ? input.summary : {};
  const gui = isObject(input.gui) ? input.gui : {};
  const outputs = isObject(input.outputs) ? input.outputs : {};
  const approval = isObject(input.approval) ? input.approval : {};
  const course = isObject(input.course) ? input.course : {};
  const errors = Array.isArray(input.errors) ? input.errors : [];
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
      courseId: course.courseId ?? "",
      name: course.name ?? selectedCourse().name,
      section: course.section ?? selectedCourse().section,
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

function resetEditableValues() {
  state.editableValues = Object.fromEntries(
    state.agentOutput.gui.editableFields.map((field) => [
      field.fieldId,
      field.value ?? "",
    ]),
  );
  state.fieldErrors = {};
  state.posted = false;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function selectedCourse() {
  return courses.find((course) => course.courseId === state.selectedCourseId);
}

function selectedAssignment() {
  return assignments.find(
    (assignment) => assignment.courseWorkId === state.selectedAssignmentId,
  );
}

function render() {
  app.innerHTML = state.isLoggedIn ? renderShell() : renderLogin();
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
        <button class="button primary" data-action="login">Googleでログイン</button>
      </section>
    </main>
  `;
}

function renderShell() {
  return `
    <div class="layout">
      <aside class="sidebar">
        <div class="brand">
          <span class="brand-mark">C</span>
          <span>Classroom支援</span>
        </div>
        <div class="sidebar-context">
          <strong>${escapeHtml(selectedCourse().name)}</strong>
          <span class="subtle">${escapeHtml(selectedCourse().section)} / ${selectedCourse().studentCount}名</span>
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
              <span class="badge">${escapeHtml(selectedCourse().name)} / ${escapeHtml(selectedCourse().section)}</span>
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
          ${renderScenarioControl()}
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

function renderScenarioControl() {
  const modes = [
    ["ready", "正常"],
    ["loading", "読込"],
    ["empty", "空"],
    ["partial", "部分"],
    ["error", "失敗"],
  ];
  return `
    <section class="toolbar" aria-label="データ状態">
      ${renderWorkflow()}
      <div class="segmented" role="group" aria-label="データ状態">
        ${modes
          .map(
            ([mode, label]) => `
              <button class="segment${state.scenario === mode ? " active" : ""}" data-scenario="${mode}" aria-pressed="${state.scenario === mode}">
                ${label}
              </button>
            `,
          )
          .join("")}
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
          <p class="subtle">Classroom情報とAI出力を読み込んでいます。</p>
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
      <h2>表示できるデータがありません</h2>
      <p class="subtle">対象コースまたは課題を変更して再取得してください。</p>
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
          <p class="subtle">教師が確認対象のコースを選び、提出状況のダッシュボードへ進みます。</p>
        </div>
        <span class="badge">モックデータ</span>
      </div>
      <div class="grid cols-2">
        ${courses
          .map(
            (course) => `
              <article class="card ${course.courseId === state.selectedCourseId ? "selected" : ""}">
                <div class="card-header">
                  <h3>${escapeHtml(course.name)}</h3>
                  ${course.courseId === state.selectedCourseId ? '<span class="badge success">選択中</span>' : ""}
                </div>
                <p class="subtle">${escapeHtml(course.section)} / ${course.studentCount}名 / 更新 ${escapeHtml(course.updatedAt)}</p>
                <div class="action-row" style="margin-top: 16px">
                  <button class="button primary" data-course="${course.courseId}">このコースを開く</button>
                </div>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderDashboard() {
  const assignment = selectedAssignment();
  return `
    <section class="band">
      <div class="grid cols-3">
        ${metricCard("未提出課題", String(assignments.length), "対応が必要な課題数", "danger")}
        ${metricCard("期限接近", "1", "3日以内に締切の課題", "warning")}
        ${metricCard("最近のお知らせ", "4", "直近7日間の投稿", "success")}
      </div>
    </section>
    <section class="band">
      <div class="section-heading">
        <div>
          <h2>最近の課題</h2>
          <p class="subtle">Classroomから取得した事実データをもとに、対応優先度を確認します。</p>
        </div>
        <button class="button" data-view="assignment">課題詳細へ</button>
      </div>
      ${renderAssignmentTable([assignment])}
    </section>
    <section class="card">
      <div class="card-header">
        <h3>AIによる注意点</h3>
        <span class="badge warning">提案</span>
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
          <p class="subtle">提出済み、未提出、遅延を横並びで確認し、AI生成対象の課題を選びます。</p>
        </div>
        <button class="button primary" data-action="generate-reminder">リマインド文を生成</button>
      </div>
      ${renderAssignmentTable(assignments)}
    </section>
    <section class="band">
      <div class="section-heading">
        <h2>提出状況</h2>
        <span class="badge warning">未提出者を確認</span>
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
            .map(
              (item) => `
                <tr class="${item.courseWorkId === state.selectedAssignmentId ? "selected-row" : ""}">
                  <td>${escapeHtml(item.title)}</td>
                  <td>${escapeHtml(item.dueDate)} ${escapeHtml(item.dueTime)}</td>
                  <td><span class="badge success">${item.turnedIn}</span></td>
                  <td><span class="badge danger">${item.missing}</span></td>
                  <td><span class="badge warning">${item.late}</span></td>
                  <td>
                    <span class="badge">${escapeHtml(item.state)}</span>
                    <button class="button ghost compact" data-assignment="${item.courseWorkId}">選択</button>
                  </td>
                </tr>
              `,
            )
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
      ${output.gui.cards.length > 0 ? `<div class="grid cols-3">${output.gui.cards
        .map((card, index) => metricCard(card.title, card.value, card.description, ["danger", "warning", "success"][index] ?? ""))
        .join("")}</div>` : renderInlineEmpty("カード表示用データはありません。")}
    </section>
    <section class="review-layout">
      <div class="card">
        <div class="card-header">
          <h3>編集</h3>
          <span class="badge">教師確認</span>
        </div>
        <div class="grid" style="margin-top: 14px">
          ${output.gui.editableFields.length > 0 ? output.gui.editableFields.map(renderEditableField).join("") : renderInlineEmpty("編集可能な項目はありません。")}
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
      ${output.gui.tables.length > 0 ? output.gui.tables.map(renderAgentTableSection).join("") : renderInlineEmpty("表形式のデータはありません。")}
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
      ${state.agentOutput.outputs.markdown ? `<pre class="output-preview">${escapeHtml(state.agentOutput.outputs.markdown.content)}</pre>` : renderInlineEmpty("Markdown出力はありません。")}
    </section>
  `;
}

function renderConfirm() {
  const title = state.editableValues.reminder_title ?? state.agentOutput.outputs.classroomReminder?.title ?? "";
  const body = state.editableValues.reminder_body ?? state.agentOutput.outputs.classroomReminder?.text ?? "";
  const canPost = Boolean(state.agentOutput.outputs.classroomReminder) && validateEditableFields(false);
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
          <p>コース全体</p>
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
    <section class="action-row">
      <button class="button primary" data-action="approve-post" ${state.posted || !canPost ? "disabled" : ""}>投稿する</button>
      <button class="button" data-view="review">文面を修正</button>
      ${state.posted ? '<span class="badge success">投稿済みとして記録しました</span>' : ""}
      ${!canPost ? '<span class="badge warning">投稿内容を確認してください</span>' : ""}
    </section>
  `;
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

function applyScenario(mode) {
  state.scenario = mode;
  if (mode === scenarioModes.partial) {
    state.agentOutput = normalizeAgentOutput(rawAgentOutputs.partial);
  } else if (mode === scenarioModes.error) {
    state.agentOutput = normalizeAgentOutput(rawAgentOutputs.error);
  } else {
    state.agentOutput = normalizeAgentOutput(rawAgentOutputs.success);
  }
  resetEditableValues();
}

function bindEvents() {
  document.querySelectorAll("[data-action='login']").forEach((button) => {
    button.addEventListener("click", () => {
      state.isLoggedIn = true;
      state.view = "courses";
      render();
    });
  });

  document.querySelectorAll("[data-action='logout']").forEach((button) => {
    button.addEventListener("click", () => {
      state.isLoggedIn = false;
      state.view = "login";
      applyScenario("ready");
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

  document.querySelectorAll("[data-scenario]").forEach((button) => {
    button.addEventListener("click", () => {
      applyScenario(button.dataset.scenario);
      render();
    });
  });

  document.querySelectorAll("[data-course]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedCourseId = button.dataset.course;
      state.view = "dashboard";
      render();
    });
  });

  document.querySelectorAll("[data-assignment]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedAssignmentId = button.dataset.assignment;
      render();
    });
  });

  document.querySelectorAll("[data-action='generate-reminder']").forEach((button) => {
    button.addEventListener("click", () => {
      applyScenario("ready");
      state.view = "review";
      render();
    });
  });

  document.querySelectorAll("[data-action='retry']").forEach((button) => {
    button.addEventListener("click", () => {
      applyScenario("ready");
      render();
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
      if (!validateEditableFields(true)) {
        state.view = "review";
        render();
        return;
      }
      state.posted = true;
      render();
    });
  });
}
