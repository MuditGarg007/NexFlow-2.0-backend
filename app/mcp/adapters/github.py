import httpx
from app.mcp.base import BaseMCPTool
from app.mcp.registry import register_tool

GITHUB_API = "https://api.github.com"


class GitHubListRepos(BaseMCPTool):
    name = "github.list_repos"
    description = "List repositories for the authenticated GitHub user. Can filter by type (all, owner, member)."
    integration_id = "github"
    status = "stable"
    input_schema = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["all", "owner", "member"], "default": "owner"},
            "sort": {"type": "string", "enum": ["created", "updated", "pushed", "full_name"], "default": "updated"},
            "per_page": {"type": "integer", "default": 10, "maximum": 100},
        },
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        self._check_status()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API}/user/repos",
                headers={"Authorization": f"Bearer {oauth_token}", "Accept": "application/vnd.github+json"},
                params=params,
            )
            resp.raise_for_status()
            repos = resp.json()
            return {"repos": [{"name": r["name"], "full_name": r["full_name"], "description": r.get("description"), "url": r["html_url"], "stars": r["stargazers_count"], "language": r.get("language")} for r in repos]}


class GitHubCreateIssue(BaseMCPTool):
    name = "github.create_issue"
    description = "Create a new issue in a GitHub repository."
    integration_id = "github"
    status = "stable"
    input_schema = {
        "type": "object",
        "properties": {
            "owner": {"type": "string", "description": "Repository owner"},
            "repo": {"type": "string", "description": "Repository name"},
            "title": {"type": "string", "description": "Issue title"},
            "body": {"type": "string", "description": "Issue body"},
            "labels": {"type": "array", "items": {"type": "string"}, "default": []},
        },
        "required": ["owner", "repo", "title"],
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        self._check_status()
        owner = params.pop("owner")
        repo = params.pop("repo")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues",
                headers={"Authorization": f"Bearer {oauth_token}", "Accept": "application/vnd.github+json"},
                json=params,
            )
            resp.raise_for_status()
            issue = resp.json()
            return {"issue_number": issue["number"], "url": issue["html_url"], "title": issue["title"]}


class GitHubListPRs(BaseMCPTool):
    name = "github.list_pull_requests"
    description = "List pull requests for a GitHub repository."
    integration_id = "github"
    status = "stable"
    input_schema = {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
            "per_page": {"type": "integer", "default": 10},
        },
        "required": ["owner", "repo"],
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        self._check_status()
        owner = params.pop("owner")
        repo = params.pop("repo")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
                headers={"Authorization": f"Bearer {oauth_token}", "Accept": "application/vnd.github+json"},
                params=params,
            )
            resp.raise_for_status()
            prs = resp.json()
            return {"pull_requests": [{"number": pr["number"], "title": pr["title"], "state": pr["state"], "url": pr["html_url"], "user": pr["user"]["login"]} for pr in prs]}


class GitHubSearchRepos(BaseMCPTool):
    name = "github.search_repos"
    description = "Search GitHub repositories by query."
    integration_id = "github"
    status = "stable"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "per_page": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    }

    async def execute(self, params: dict, oauth_token: str) -> dict:
        self._check_status()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API}/search/repositories",
                headers={"Authorization": f"Bearer {oauth_token}", "Accept": "application/vnd.github+json"},
                params={"q": params["query"], "per_page": params.get("per_page", 5)},
            )
            resp.raise_for_status()
            data = resp.json()
            return {"results": [{"name": r["full_name"], "description": r.get("description"), "stars": r["stargazers_count"], "url": r["html_url"]} for r in data.get("items", [])]}


def register_tools():
    for tool_cls in [GitHubListRepos, GitHubCreateIssue, GitHubListPRs, GitHubSearchRepos]:
        register_tool(tool_cls())
