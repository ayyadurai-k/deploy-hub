export type User = {
  id: number;
  email: string;
  display_name: string;
  date_joined: string;
  has_google: boolean;
  has_github: boolean;
};

export type Repository = {
  id: number;
  github_repo_id: number;
  name: string;
  full_name: string;
  private: boolean;
  default_branch: string;
  description: string;
  html_url: string;
  github_created_at: string | null;
  github_pushed_at: string | null;
};

export type Project = {
  id: number;
  name: string;
  slug: string;
  status: "draft";
  repository: number | null;
  created_at: string;
  updated_at: string;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type SyncResponse = {
  synced: number;
  status: "pending" | "in_progress" | "success" | "failure";
};
