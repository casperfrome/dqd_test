import type { DatabaseAccessLevel, PostCategory } from "../api/types";

export type ViewKey = "circles" | "profile" | "analytics" | "admin" | "databases" | "code";
export type AuthMode = "login" | "register";
export type NoticeKind = "success" | "error" | "info";

export interface Notice {
  id: number;
  kind: NoticeKind;
  text: string;
}

export const categoryLabels: Record<PostCategory, string> = {
  discussion: "讨论",
  news: "新闻",
  transfer: "转会",
  match: "比赛",
  off_topic: "闲聊",
};

export const categoryOptions = Object.keys(categoryLabels) as PostCategory[];

export const roleLabels: Record<string, string> = {
  super_admin: "超级管理员",
  fan_circle_owner: "圈主",
  normal_user: "普通用户",
};

export const databaseAccessLabels: Record<DatabaseAccessLevel, string> = {
  public: "公开访问",
  authenticated: "登录用户",
  super_admin: "超级管理员",
};

export const aiFactTypeLabels: Record<string, string> = {
  database: "数据库",
  table: "表",
  column: "字段",
  index: "索引",
  foreign_key: "外键",
  sample_rows: "样例",
};

export function viewTitle(view: ViewKey) {
  const titles: Record<ViewKey, string> = {
    circles: "球迷圈总览",
    profile: "用户资料",
    analytics: "社区分析",
    admin: "权限管理",
    databases: "数据库",
    code: "代码问答",
  };
  return titles[view];
}
