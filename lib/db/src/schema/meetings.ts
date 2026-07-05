import {
  pgTable, serial, text, integer, timestamp, jsonb, pgEnum, boolean, real
} from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const meetingStatusEnum = pgEnum("meeting_status", [
  "pending", "processing", "indexed", "failed"
]);

export const entityTypeEnum = pgEnum("entity_type", [
  "person", "project", "topic", "decision", "task", "risk",
  "blocker", "document", "question", "deadline"
]);

export const decisionStatusEnum = pgEnum("decision_status", [
  "active", "revised", "superseded", "implemented", "rejected"
]);

export const taskStatusEnum = pgEnum("task_status", [
  "open", "in_progress", "completed", "blocked", "overdue"
]);

export const projectStatusEnum = pgEnum("project_status", [
  "active", "completed", "on_hold", "archived"
]);

export const decisionActionEnum = pgEnum("decision_action", [
  "created", "updated", "superseded", "confirmed", "rejected"
]);

export const activityTypeEnum = pgEnum("activity_type", [
  "meeting_added", "decision_made", "task_created",
  "decision_updated", "entity_merged", "memory_improved"
]);

export const chatRoleEnum = pgEnum("chat_role", ["user", "assistant"]);

// ─── MEETINGS ────────────────────────────────────────────────────────────────
export const meetingsTable = pgTable("meetings", {
  id: serial("id").primaryKey(),
  title: text("title").notNull(),
  date: timestamp("date").notNull(),
  status: meetingStatusEnum("status").notNull().default("pending"),
  transcript: text("transcript").notNull(),
  summary: text("summary"),
  contentType: text("content_type").notNull().default("transcript"),
  durationMinutes: integer("duration_minutes"),
  tags: jsonb("tags").$type<string[]>().default([]),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const insertMeetingSchema = createInsertSchema(meetingsTable).omit({ id: true, createdAt: true });
export type InsertMeeting = z.infer<typeof insertMeetingSchema>;
export type Meeting = typeof meetingsTable.$inferSelect;

// ─── ENTITIES ────────────────────────────────────────────────────────────────
export const entitiesTable = pgTable("entities", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  type: entityTypeEnum("type").notNull(),
  description: text("description"),
  firstSeen: timestamp("first_seen").defaultNow(),
  lastSeen: timestamp("last_seen").defaultNow(),
  attributes: jsonb("attributes").$type<Record<string, unknown>>().default({}),
  isCanonical: boolean("is_canonical").default(true),
  canonicalId: integer("canonical_id"),
});

export const insertEntitySchema = createInsertSchema(entitiesTable).omit({ id: true });
export type InsertEntity = z.infer<typeof insertEntitySchema>;
export type Entity = typeof entitiesTable.$inferSelect;

// ─── MEETING_ENTITIES ─────────────────────────────────────────────────────────
export const meetingEntitiesTable = pgTable("meeting_entities", {
  id: serial("id").primaryKey(),
  meetingId: integer("meeting_id").notNull().references(() => meetingsTable.id, { onDelete: "cascade" }),
  entityId: integer("entity_id").notNull().references(() => entitiesTable.id, { onDelete: "cascade" }),
  mentionCount: integer("mention_count").default(1),
  context: text("context"),
});

// ─── ENTITY_RELATIONSHIPS ─────────────────────────────────────────────────────
export const entityRelationshipsTable = pgTable("entity_relationships", {
  id: serial("id").primaryKey(),
  sourceId: integer("source_id").notNull().references(() => entitiesTable.id, { onDelete: "cascade" }),
  targetId: integer("target_id").notNull().references(() => entitiesTable.id, { onDelete: "cascade" }),
  relationship: text("relationship").notNull(),
  weight: real("weight").default(1.0),
  meetingId: integer("meeting_id").references(() => meetingsTable.id, { onDelete: "set null" }),
  createdAt: timestamp("created_at").defaultNow(),
});

// ─── PROJECTS ────────────────────────────────────────────────────────────────
export const projectsTable = pgTable("projects", {
  id: serial("id").primaryKey(),
  entityId: integer("entity_id").notNull().references(() => entitiesTable.id, { onDelete: "cascade" }),
  name: text("name").notNull(),
  description: text("description"),
  status: projectStatusEnum("status").notNull().default("active"),
  createdAt: timestamp("created_at").defaultNow(),
});

// ─── DECISIONS ────────────────────────────────────────────────────────────────
export const decisionsTable = pgTable("decisions", {
  id: serial("id").primaryKey(),
  title: text("title").notNull(),
  description: text("description"),
  status: decisionStatusEnum("status").notNull().default("active"),
  meetingId: integer("meeting_id").notNull().references(() => meetingsTable.id, { onDelete: "cascade" }),
  projectId: integer("project_id").references(() => projectsTable.id, { onDelete: "set null" }),
  assignedTo: text("assigned_to"),
  pros: jsonb("pros").$type<string[]>().default([]),
  cons: jsonb("cons").$type<string[]>().default([]),
  reasons: jsonb("reasons").$type<string[]>().default([]),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

// ─── DECISION_HISTORY ─────────────────────────────────────────────────────────
export const decisionHistoryTable = pgTable("decision_history", {
  id: serial("id").primaryKey(),
  decisionId: integer("decision_id").notNull().references(() => decisionsTable.id, { onDelete: "cascade" }),
  meetingId: integer("meeting_id").notNull().references(() => meetingsTable.id, { onDelete: "cascade" }),
  action: decisionActionEnum("action").notNull(),
  description: text("description").notNull(),
  previousValue: text("previous_value"),
  newValue: text("new_value"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

// ─── TASKS ────────────────────────────────────────────────────────────────────
export const tasksTable = pgTable("tasks", {
  id: serial("id").primaryKey(),
  title: text("title").notNull(),
  description: text("description"),
  status: taskStatusEnum("status").notNull().default("open"),
  assignedTo: text("assigned_to"),
  dueDate: timestamp("due_date"),
  meetingId: integer("meeting_id").notNull().references(() => meetingsTable.id, { onDelete: "cascade" }),
  projectId: integer("project_id").references(() => projectsTable.id, { onDelete: "set null" }),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

// ─── CHAT_MESSAGES ────────────────────────────────────────────────────────────
export const chatMessagesTable = pgTable("chat_messages", {
  id: serial("id").primaryKey(),
  conversationId: text("conversation_id").notNull(),
  role: chatRoleEnum("role").notNull(),
  content: text("content").notNull(),
  sourcesJson: jsonb("sources_json").$type<unknown[]>().default([]),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

// ─── ACTIVITY_LOG ────────────────────────────────────────────────────────────
export const activityLogTable = pgTable("activity_log", {
  id: serial("id").primaryKey(),
  type: activityTypeEnum("type").notNull(),
  title: text("title").notNull(),
  description: text("description"),
  entityId: integer("entity_id"),
  meetingId: integer("meeting_id"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});
