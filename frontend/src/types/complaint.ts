export interface Session {
  session_id: string;
  created_at: string;
  last_updated: string;
  status: string;
}

export interface Complaint {
  company_name: string | null;
  manufacturer: string | null;

  product_name: string | null;
  generic_name: string | null;
  strength: string | null;
  dosage_form: string | null;
  pack_size: string | null;

  batch_number: string | null;
  manufacturing_date: string | null;
  expiry_date: string | null;

  quantity: string | null;

  complaint_description: string | null;
  complaint_category: string | null;
  complaint_type: string | null;
  defect_type: string | null;

  severity: string | null;

  reported_event: string | null;
  symptoms: string[];
}

export interface AI {
  summary: string | null;
  confidence: number | null;

  missing_fields: string[];

  next_question?: string | null;

  extraction_status?: string | null;

  reasoning?: string | null;
}

export interface ValidationError {
  field: string;
  message: string;
}

export interface Validation {
  is_valid: boolean;
  errors: ValidationError[];
  warnings: string[];
  missing_fields: string[];
  validation_timestamp: string | null;
}

export interface Risk {
  priority: string | null;
  score: number | null;
  risk_factors: string[];
  reasons: string[];
  recommended_actions: string[];
  assessment_timestamp: string | null;
}

export interface ComplaintState {
  session: Session;
  complaint: Complaint;
  ai: AI;
  validation: Validation;
  risk: Risk;
}

export interface ComplaintResponse {
  success: boolean;
  message: string;
  data: ComplaintState;
}

export interface ComplaintCreateRequest {
  message: string;
}