// ─── Status Enums ──────────────────────────────────────────────────────────────

export type ProjectStatus =
  | "pending"
  | "running"
  | "waiting_review"
  | "completed"
  | "failed"
  | "cancelled";

export type RunStatus =
  | "pending"
  | "running"
  | "waiting_review"
  | "completed"
  | "failed"
  | "cancelled";

export type AgentStep =
  | "requirements_analysis"
  | "architecture_design"
  | "code_generation"
  | "validation"          // ← Added
  | "test_writing"
  | "code_review"
  | "devops_setup"
  | "documentation"
  | "packaging"
  | "completed"
  | "cancelled";

// ─── Project & Run Models ──────────────────────────────────────────────────────

export interface VisualReference {
  type: 'url' | 'upload';
  url?: string;
  file_name?: string;
  s3_key?: string;
  description?: string;
  preview_url?: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  requirements: string;
  target_language: string;
  target_framework?: string;
  visual_references?: VisualReference[];
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description: string;
  requirements: string;
  target_language: string;
  target_framework?: string;
  visual_references?: VisualReference[];
}

export interface RunEvent {
  id: string;
  run_id: string;
  event_type: string;
  agent_name?: string;
  step?: string;
  message: string;
  data?: Record<string, any>;
  created_at: string;
}

export interface ProjectRun {
  id: string;
  project_id: string;
  thread_id: string;
  status: RunStatus;
  current_step?: string;
  interrupt_payload?: InterruptPayload;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  events: RunEvent[];
}

// ─── Human Review / Feedback ──────────────────────────────────────────────────

export interface HumanFeedback {
  action: "approve" | "reject" | "modify";
  feedback?: string;
  modifications?: Record<string, any>;
}

export interface FeedbackResponse {
  status: string;
  action: string;
}

export interface CancelResponse {
  status: string;
  message: string;
}

// ─── Interrupt Payload ────────────────────────────────────────────────────────

export interface ValidationSummary {
  total_validated: number;
  auto_fixed_count: number;
  auto_fixed_files: string[];
  remaining_issues: Array<{ path: string; errors: ValidationError[] }>;
  remaining_count: number;
}

export interface ValidationError {
  check: string;
  output: string;
  line?: number | null;
  line_hint?: string;
}

export interface InterruptPayload {
  step: string;
  title: string;
  description: string;
  data: {
    // requirements_analysis
    specification?: Specification;
    // architecture_design
    architecture?: Architecture;
    // code_review
    code_files?: CodeFile[];
    test_files?: TestFile[];
    review_comments?: ReviewComments;
    validation_summary?: ValidationSummary;  // ← Added
    files_summary?: FileSummary[];
    // final_review
    all_files?: FileInfo[];
    total_files?: number;
    code_files_count?: number;
    test_files_count?: number;
    devops_files_count?: number;
    doc_files_count?: number;
    review_score?: number;
    summary?: string;
    auto_fixed_count?: number;
    human_feedback_history?: Array<{
      step: string;
      action: string;
      feedback: string;
    }>;
  };
}

// ─── Artifacts ────────────────────────────────────────────────────────────────

export interface Artifact {
  id: string;
  project_id: string;
  run_id?: string;
  name: string;
  artifact_type: string;
  file_path: string;
  language?: string;
  size_bytes?: number;
  is_approved: boolean;
  created_at: string;
}

export interface ArtifactContent {
  content: string;
  language?: string;
  file_path: string;
}

export interface DownloadUrlResponse {
  url: string;
}

export interface RunStateResponse {
  state: Record<string, any> | null;
}

// ─── Code / File Models ───────────────────────────────────────────────────────

export interface CodeFile {
  path: string;
  content: string;
  description?: string;
  component?: string;
  language?: string;
  type?: string;
}

export interface TestFile {
  path: string;
  content: string;
  source_file?: string;
  language?: string;
  type?: string;
}

export interface FileSummary {
  path: string;
  language: string;
  type: "source" | "test";
  was_fixed?: boolean;
}

export interface FileInfo {
  path: string;
  type: string;
  language?: string;
}

// ─── Specification Models ─────────────────────────────────────────────────────

export interface Specification {
  project_name: string;
  project_summary: string;
  target_language: string;
  target_framework: string;
  functional_requirements: FunctionalRequirement[];
  non_functional_requirements: NonFunctionalRequirement[];
  data_models: DataModel[];
  api_endpoints: ApiEndpoint[];
  user_roles: UserRole[];
  tech_stack: TechStack;
  constraints: string[];
  assumptions: string[];
  open_questions: string[];
  out_of_scope: string[];
  glossary: GlossaryEntry[];
}

export interface FunctionalRequirement {
  id: string;
  title: string;
  description: string;
  priority: "must" | "should" | "could";
  user_story: string;
  acceptance_criteria: string[];
  affected_entities: string[];
}

export interface NonFunctionalRequirement {
  id: string;
  category: string;
  description: string;
  metric: string;
  implementation_hint?: string;
}

export interface UserRole {
  name: string;
  description: string;
  permissions: string[];
}

export interface DataModel {
  name: string;
  description: string;
  fields: Field[];
  relationships: Relationship[];
  business_rules: string[];
}

export interface Field {
  name: string;
  type: string;
  required: boolean;
  unique?: boolean;
  indexed?: boolean;
  description: string;
  validation_rules?: string[];
}

export interface Relationship {
  type: string;
  target: string;
  description: string;
}

export interface ApiEndpoint {
  method: string;
  path: string;
  description: string;
  auth_required: boolean;
  required_roles?: string[];
}

export interface TechStack {
  language: string;
  framework: string;
  database: string;
  cache?: string;
  auth?: string;
  testing?: string;
  orm?: string;
  observability?: string;
  ci_cd?: string;
  containerisation?: string;
  [key: string]: string | undefined;
}

export interface GlossaryEntry {
  term: string;
  definition: string;
}

// ─── Architecture Models ──────────────────────────────────────────────────────

export interface Architecture {
  architecture_pattern: string;
  components: Component[];
  files_to_generate: GenerateFile[];
  database_schema: DatabaseSchema;
  design_decisions: DesignDecision[];
  key_patterns: string[];
  security_considerations: string[];
  scalability_notes: string[];
}

export interface Component {
  name: string;
  layer: string;
  responsibility: string;
  dependencies: string[];
  files: string[];
}

export interface GenerateFile {
  path: string;
  description: string;
  component: string;
  priority: number;
  dependencies: string[];
}

export interface DatabaseSchema {
  type: string;
  tables: Table[];
}

export interface Table {
  name: string;
  columns: Column[];
  indexes: string[];
  foreign_keys: string[];
}

export interface Column {
  name: string;
  type: string;
  constraints: string[];
}

export interface DesignDecision {
  decision: string;
  rationale: string;
  alternatives: string[];
}

// ─── Review Models ────────────────────────────────────────────────────────────

export interface ReviewComments {
  overall_score: number;
  total_issues: number;
  summary: string;
  critical_issues: ReviewIssue[];
  warnings: ReviewIssue[];
  improvements: ReviewImprovement[];
  security_assessment: SecurityAssessment;
  test_coverage_assessment: CoverageAssessment;
  approved: boolean;
}

export interface ReviewIssue {
  file: string;
  line_hint?: string;
  category: string;
  description: string;
  suggestion: string;
}

export interface ReviewImprovement {
  file: string;
  category: string;
  description: string;
  benefit: string;
}

export interface SecurityAssessment {
  score: number;
  vulnerabilities: string[];
  recommendations: string[];
}

export interface CoverageAssessment {
  estimated_coverage: number;
  missing_tests: string[];
  recommendations: string[];
}

// ─── WebSocket Message ────────────────────────────────────────────────────────

export interface WsMessage {
  type: string;
  agent?: string;
  step?: string;
  message: string;
  data?: Record<string, any>;
  payload?: InterruptPayload;
}
