// Types for the lifecycle viewer. Defined locally (not generated into
// api-types.ts) so the viewer is self-contained and doesn't disturb the
// template's existing Item types.

export interface Batch {
  id: string;
  source_filename: string;
  status: string;
  clean_count: number;
  error_count: number;
  created_at: string;
}

export interface LifecycleTransition {
  name: string;
  label: string;
  from: string[];
  to: string;
  roles: string[];
  guard_text: string | null;
}

export interface LifecycleInvariant {
  name: string;
  label: string;
  text: string;
}

export interface LifecycleSpec {
  name: string;
  title: string;
  version: number;
  digest: string;
  states: { id: string; description: string }[];
  transitions: LifecycleTransition[];
  invariants: LifecycleInvariant[];
}

export interface AvailableAction {
  action: string;
  control_id: string;
  to: string;
  allowed: boolean;
  reason: string;
}

export interface AvailableActions {
  batch_id: string;
  status: string;
  version: number;
  spec_version: number;
  spec_digest: string;
  actions: AvailableAction[];
}

export interface RuleEvaluation {
  control_id: string;
  result: boolean;
  inputs: Record<string, unknown>;
}

export interface LifecycleEvent {
  id: string;
  occurred_at: string;
  action: string;
  previous_state: string;
  new_state: string;
  actor_id: string | null;
  actor_roles: string[];
  spec_name: string;
  spec_version: number;
  spec_digest: string;
  summary: string;
  guard_results: RuleEvaluation[];
  invariant_results: RuleEvaluation[];
}
