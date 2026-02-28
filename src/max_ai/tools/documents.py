"""Document management tools — create, read, edit, archive, list, search markdown docs."""

from typing import Any

from max_ai.persistence import DocumentStore
from max_ai.tools.base import BaseTool, ToolDefinition


class DocumentTools(BaseTool):
    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="document_create",
                description="Create a new markdown document with the given title and content.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Unique title for the document"},
                        "content": {"type": "string", "description": "Markdown content of the document"},
                    },
                    "required": ["title", "content"],
                },
            ),
            ToolDefinition(
                name="document_read",
                description="Return the full content of a document by title.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Title of the document to read"},
                    },
                    "required": ["title"],
                },
            ),
            ToolDefinition(
                name="document_edit",
                description="Update the title and/or content of an existing document.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Current title of the document"},
                        "new_title": {"type": "string", "description": "New title (optional)"},
                        "new_content": {"type": "string", "description": "New content (optional)"},
                    },
                    "required": ["title"],
                },
            ),
            ToolDefinition(
                name="document_archive",
                description="Archive (soft-delete) a document by title.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Title of the document to archive"},
                    },
                    "required": ["title"],
                },
            ),
            ToolDefinition(
                name="document_list",
                description="List all documents with their status and dates.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "include_archived": {
                            "type": "boolean",
                            "description": "Include archived documents (default: false)",
                        },
                    },
                    "required": [],
                },
            ),
            ToolDefinition(
                name="document_search",
                description="Search document titles and content for a query string. Returns matching active documents.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            ),
        ]

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        try:
            if tool_name == "document_create":
                return await self._store.create(tool_input["title"], tool_input["content"])

            elif tool_name == "document_read":
                doc = await self._store.get_by_title(tool_input["title"])
                if doc is None:
                    return f"Document '{tool_input['title']}' not found."
                return f"# {doc['title']}\n\n{doc['content']}"

            elif tool_name == "document_edit":
                return await self._store.edit(
                    tool_input["title"],
                    new_title=tool_input.get("new_title"),
                    new_content=tool_input.get("new_content"),
                )

            elif tool_name == "document_archive":
                return await self._store.archive(tool_input["title"])

            elif tool_name == "document_list":
                include_archived = tool_input.get("include_archived", False)
                docs = await self._store.list_all(include_archived=include_archived)
                if not docs:
                    return "No documents found."
                lines = [f"- **{d['title']}** [{d['status']}] — created {d['created_at'][:10]}" for d in docs]
                return "\n".join(lines)

            elif tool_name == "document_search":
                docs = await self._store.search(tool_input["query"])
                if not docs:
                    return f"No documents found matching '{tool_input['query']}'."
                lines = [f"- **{d['title']}** — updated {d['updated_at'][:10]}" for d in docs]
                return "\n".join(lines)

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            return f"Error: {e}"
