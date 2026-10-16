import { z } from "zod";

export const CategoryEnum = z.enum([
  "how-to",
  "troubleshooting",
  "project",
  "refund",
  "complaint",
  "quote",
  "follow-up",
]);
export type Category = z.infer<typeof CategoryEnum>;

export const RiskLevelEnum = z.enum(["low", "medium", "high"]);
export type RiskLevel = z.infer<typeof RiskLevelEnum>;

export const UrgencyEnum = z.enum(["low", "medium", "high"]);
export type Urgency = z.infer<typeof UrgencyEnum>;

export const HumanActionEnum = z.enum(["approve", "edit", "reject", "expert"]);
export type HumanAction = z.infer<typeof HumanActionEnum>;

export const EmailSchema = z.object({
  id: z.string(),
  subject: z.string(),
  from: z.string(),
  body: z.string(),
  expected_category: CategoryEnum.optional(),
  expected_risk: RiskLevelEnum.optional(),
  expected_urgency: UrgencyEnum.optional(),
  key_facts: z.array(z.string()).optional(),
  expected_behavior: z.string().optional(),
  expected_article: z.string().nullable().optional(),
  is_holdout: z.boolean().default(false),
});
export type EmailMessage = z.infer<typeof EmailSchema>;

export const ClassificationSchema = z.object({
  category: CategoryEnum,
  subcategory: z.string().default("general"),
  risk_level: RiskLevelEnum,
  urgency: UrgencyEnum,
  confidence: z.number().min(0).max(1).default(0.85),
  key_facts: z.array(z.string()).default([]),
  knowledge_query: z.string().nullable().default(null),
  reasoning: z.string().default(""),
});
export type Classification = z.infer<typeof ClassificationSchema>;

export const SourceRefSchema = z.object({
  title: z.string(),
  url: z.string(),
  relevance: z.number().optional(),
});
export type SourceRef = z.infer<typeof SourceRefSchema>;

export const DraftReplySchema = z.object({
  category: z.string(),
  summary: z.string(),
  suggested_reply: z.string(),
  sources: z.array(SourceRefSchema).default([]),
  risk_level: RiskLevelEnum,
  needs_human_approval: z.boolean().default(true),
  next_action: z.string().default("Send response to customer"),
});
export type DraftReply = z.infer<typeof DraftReplySchema>;

export const HumanReviewRequestSchema = z.object({
  interaction_id: z.string(),
  action: HumanActionEnum,
  edited_text: z.string().optional(),
  correction_reason: z.string().optional(),
  reviewer: z.string().default("Operator"),
});
export type HumanReviewRequest = z.infer<typeof HumanReviewRequestSchema>;
