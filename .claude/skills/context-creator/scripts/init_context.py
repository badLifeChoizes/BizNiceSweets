#!/usr/bin/env python3
"""
Project Context Initializer - Creates a new project context skill from template

Usage:
    init_context.py <project-name> --path <path>

Examples:
    init_context.py my-webapp --path .claude/skills
    init_context.py firmware-project --path /custom/location
"""

import sys
from pathlib import Path
from datetime import datetime


def title_case(name: str) -> str:
    """Convert hyphenated name to Title Case."""
    return ' '.join(word.capitalize() for word in name.split('-'))


def load_template(template_path: Path) -> str:
    """Load a template file and return its contents."""
    if template_path.exists():
        return template_path.read_text()
    return ""


def apply_substitutions(content: str, project_name: str, project_title: str) -> str:
    """Apply template substitutions."""
    today = datetime.now().strftime("%Y-%m-%d")

    substitutions = {
        "{{PROJECT_NAME}}": project_name,
        "{{PROJECT_TITLE}}": project_title,
        "{{DATE}}": today,
        "{{PROJECT_DESCRIPTION}}": "[TODO: Describe what this project does]",
        "{{RUN_COMMAND}}": "[TODO: Add run command]",
        "{{TEST_COMMAND}}": "[TODO: Add test command]",
        "{{BUILD_COMMAND}}": "[TODO: Add build command]",
        "{{ABSTRACTION_LAYER}}": "[abstraction layer]",
        "{{RESOURCE}}": "[resource]",
        "{{LOGGING_FRAMEWORK}}": "[logging framework]",
    }

    for placeholder, value in substitutions.items():
        content = content.replace(placeholder, value)

    return content


def init_context(project_name: str, output_path: str) -> Path | None:
    """
    Initialize a new project context skill.

    Args:
        project_name: Name of the project (hyphen-case)
        output_path: Directory where context skill will be created

    Returns:
        Path to created skill directory, or None if error
    """
    # Determine paths
    skill_name = f"{project_name}-context"
    skill_dir = Path(output_path).resolve() / skill_name

    # Get template directory (relative to this script)
    script_dir = Path(__file__).parent.parent
    template_dir = script_dir / "templates" / "project-context"

    # Check if skill already exists
    if skill_dir.exists():
        print(f"❌ Error: Skill directory already exists: {skill_dir}")
        return None

    # Check if templates exist
    if not template_dir.exists():
        print(f"❌ Error: Template directory not found: {template_dir}")
        print("   Make sure you're running from the context-creator skill directory")
        return None

    project_title = title_case(project_name)

    try:
        # Create skill directory structure
        skill_dir.mkdir(parents=True, exist_ok=False)
        (skill_dir / "references").mkdir()

        print(f"✅ Created skill directory: {skill_dir}")

        # Process and write SKILL.md
        skill_template = template_dir / "SKILL.template.md"
        if skill_template.exists():
            content = skill_template.read_text()
            content = apply_substitutions(content, project_name, project_title)
            (skill_dir / "SKILL.md").write_text(content)
            print("✅ Created SKILL.md")
        else:
            print("⚠️  SKILL.template.md not found, creating minimal SKILL.md")
            minimal = f"""---
name: {skill_name}
description: Project context for {project_name}. Use when working on this project to understand architecture, patterns, and conventions. (project)
---

# {project_title} Project Context

[TODO: Add project context]
"""
            (skill_dir / "SKILL.md").write_text(minimal)

        # Process reference templates
        ref_templates = [
            "architecture.template.md",
            "conventions.template.md",
            "gotchas.template.md",
            "workflows.template.md",
        ]

        for template_name in ref_templates:
            template_path = template_dir / "references" / template_name
            if template_path.exists():
                content = template_path.read_text()
                content = apply_substitutions(content, project_name, project_title)
                output_name = template_name.replace(".template", "")
                (skill_dir / "references" / output_name).write_text(content)
                print(f"✅ Created references/{output_name}")

        print(f"\n✅ Project context skill '{skill_name}' initialized at {skill_dir}")
        print("\n📋 Next Steps:")
        print("1. Fill in the TODO sections in SKILL.md")
        print("2. Complete the reference files with project-specific details")
        print("3. Add guardrails to keep AI agents aligned with project goals")
        print("4. Test by using the skill on a real task")
        print("\n💡 Tips:")
        print("- Run codebase-analyzer first to bootstrap content")
        print("- Focus on guardrails and gotchas - these provide the most value")
        print("- Remove sections that don't apply to your project")

        return skill_dir

    except Exception as e:
        print(f"❌ Error creating skill: {e}")
        # Cleanup on failure
        if skill_dir.exists():
            import shutil
            shutil.rmtree(skill_dir)
        return None


def main():
    if len(sys.argv) < 4 or sys.argv[2] != '--path':
        print("Usage: init_context.py <project-name> --path <path>")
        print()
        print("Creates a project context skill from template.")
        print()
        print("Arguments:")
        print("  project-name  Name of the project (hyphen-case, e.g., 'my-webapp')")
        print("  --path        Directory where the context skill will be created")
        print()
        print("Examples:")
        print("  init_context.py my-webapp --path .claude/skills")
        print("  init_context.py firmware-v2 --path /home/user/.claude/skills")
        print()
        print("The script creates a <project-name>-context/ directory with:")
        print("  - SKILL.md with structured sections for project context")
        print("  - references/architecture.md for system design details")
        print("  - references/conventions.md for coding standards")
        print("  - references/gotchas.md for non-obvious quirks")
        print("  - references/workflows.md for build/test/deploy procedures")
        sys.exit(1)

    project_name = sys.argv[1]
    output_path = sys.argv[3]

    print(f"🚀 Initializing project context skill for: {project_name}")
    print(f"   Location: {output_path}")
    print()

    result = init_context(project_name, output_path)

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
