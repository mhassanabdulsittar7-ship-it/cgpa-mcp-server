"""
server.py - the CGPA Guider's MCP server (FastMCP).

Every tool from Assignment 2 is shared here. Any MCP client (our LangGraph
agent, a friend's agent in another language, Claude Desktop...) can call them.

Local test, no LLM or key needed:
    fastmcp list server.py
    fastmcp call server.py get_credit_hours semesters='[5,6]'     # 37.0

Run as an HTTP server (the agent connects to http://127.0.0.1:8000/mcp):
    python server.py

Hosting (Horizon / Render): the platform imports/starts this file. Host and port
come from the environment so the same file works locally and online.
"""

import os

from fastmcp import FastMCP

from tools import (
    marks_to_grade_points,
    calculate_semester_gpa,
    calculate_new_cgpa,
    required_gpa_for_target,
    get_semester_courses,
    get_credit_hours,
    get_remaining_credit_hours,
    save_report,
)

mcp = FastMCP("cgpa")  # `mcp` is the object Horizon looks for: server.py:mcp

for _tool in (
    marks_to_grade_points,
    calculate_semester_gpa,
    calculate_new_cgpa,
    required_gpa_for_target,
    get_semester_courses,
    get_credit_hours,
    get_remaining_credit_hours,
    save_report,
):
    mcp.tool(_tool)  # a plain function becomes an MCP tool


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        path="/mcp",
    )
