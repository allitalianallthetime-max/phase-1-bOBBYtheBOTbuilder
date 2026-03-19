"""Agent: Claude Sonnet — Blueprint/repair procedure writer + schematic generator."""
import json
import asyncio
from worker_config import (
    ANTHROPIC_KEY, CLAUDE_MODEL, get_anthropic, log, log_event,
    truncate, estimate_tokens,
)
from agent_grok import format_grok_for_claude, format_grok_for_mechanic
from prompts import (
    mechanic_claude_system, quote_check_claude_system,
    SCHEMATIC_SYSTEM,
)


def run_claude_sync(junk_desc: str, project_type: str,
                     grok_analysis, detail_level: str,
                     conception_context: str, grok_ok: bool,
                     mode: str = "blueprint", research_text: str = "") -> dict:
    if not ANTHROPIC_KEY:
        return {"blueprint": "Claude offline.", "tokens": 0}

    token_limit = {"Standard": 4000, "Industrial": 6000, "Experimental": 8000}
    max_out = token_limit.get(detail_level, 4000)

    if mode == "mechanic":
        system = mechanic_claude_system(detail_level, conception_context, grok_ok)
        grok_text = format_grok_for_mechanic(grok_analysis)
        grok_text = truncate(grok_text, 4000)
        tools_text = truncate(junk_desc, 3000)

        user_content = (
            f"GROK-4.2 DIAGNOSTIC ANALYSIS:\n{grok_text}\n\n"
            + (f"{research_text}\n\n" if research_text else "")
            + f"REPAIR REQUEST:\n{project_type}\n\n"
            f"AVAILABLE TOOLS & PARTS:\n{tools_text}\n\n"
            f"Write the complete field repair procedure. Use ONLY available tools. "
            f"Include the emergency jury-rig option. DO NOT suggest anything "
            f"listed under ALREADY TRIED. "
            f"Reference real forum fixes, TSB numbers, and part prices from the "
            f"web research when available. Include a REFERENCES section with links."
        )
    elif mode == "quote_check":
        system = quote_check_claude_system(conception_context)
        grok_text = (json.dumps(grok_analysis, indent=2) if isinstance(grok_analysis, dict)
                     else str(grok_analysis))
        grok_text = truncate(grok_text, 4000)

        user_content = (
            f"GROK-4.2 COST ANALYSIS:\n{grok_text}\n\n"
            + (f"{research_text}\n\n" if research_text else "")
            + f"QUOTE TO CHECK:\n{project_type}\n\n"
            f"Write the complete quote analysis. Be honest — if the quote is fair, "
            f"say so. Include real part prices from web research. Check for recalls "
            f"and extended warranties. Give the vehicle owner a clear action plan."
        )
    else:
        detail_map = {
            "Standard": (
                "Complete blueprint with 10 sections. "
                "Include specific measurements and dimensions."
            ),
            "Industrial": (
                "Industrial-grade. 10 standard sections PLUS: "
                "POWER BUDGET, TORQUE CALCULATIONS, WEIGHT DISTRIBUTION, "
                "WIRING DIAGRAM, BILL OF MATERIALS, TOLERANCES."
            ),
            "Experimental": (
                "Research-grade. Everything in Industrial PLUS: "
                "FAILURE MODE ANALYSIS, THERMAL ANALYSIS, FATIGUE LIFE, "
                "CONTROL SYSTEM with PID, ALTERNATIVE DESIGNS, "
                "PERFORMANCE ENVELOPE, UPGRADE PATH."
            ),
        }

        grok_warning = ""
        if not grok_ok:
            grok_warning = (
                "\n\nWARNING: Grok's inventory analysis failed. You MUST analyze "
                "the raw inventory yourself. Do NOT rely on the Grok section below.\n"
            )

        system = (
            "You are CLAUDE-SONNET, a senior mechanical engineer on AoC3P0 Builder Foundry.\n\n"
            "CRITICAL: PROJECT GOAL is what user wants to BUILD. INVENTORY is what they OWN.\n\n"
            "DESIGN ORIGINALITY: Do NOT copy commercial designs. INVENT a novel mechanism "
            "based on what the inventory provides. Propose 2+ approaches in the overview.\n\n"
            "MATERIALS: Every part must trace to a specific inventory item.\n"
            "Exception: basic consumables (fasteners, wires, adhesives).\n\n"
            "HONESTY: Carry [EST] tags forward. Section 9: HONEST ASSESSMENT & GAPS. "
            "Section 10: BUDGET GAP-FILLER SHOPPING LIST (Harbor Freight, salvage first).\n\n"
            "10 SECTIONS: 1-Overview, 2-Materials Manifest, 3-Tools, 4-Assembly Sequence, "
            "5-Technical Specs, 6-Safety, 7-Testing, 8-Modifications, "
            "9-Honest Assessment, 10-Budget Gap-Filler.\n\n"
            + detail_map.get(detail_level, detail_map["Standard"])
            + grok_warning
            + (f"\nCONCEPTION BRIEF:\n{conception_context}" if conception_context else "")
        )

        grok_text = format_grok_for_claude(grok_analysis)
        grok_text = truncate(grok_text, 4000)
        inventory_text = truncate(junk_desc, 3000)

        user_content = (
            f"GROK-4.2 INVENTORY ANALYSIS:\n{grok_text}\n\n"
            + (f"{research_text}\n\n" if research_text else "")
            + f"PROJECT GOAL:\n{project_type}\n\n"
            f"RAW INVENTORY:\n{inventory_text}\n\n"
            f"Generate the complete blueprint. Every material must reference "
            f"which inventory item it came from. Reference real maker projects, "
            f"part prices, and build videos from the web research when available. "
            f"Include a REFERENCES section with links."
        )

    # Token budget check on input
    input_estimate = estimate_tokens(system + user_content)
    if input_estimate > 12000:
        log_event("claude_input_truncated", estimated_tokens=input_estimate)
        user_content = truncate(user_content, 8000)

    try:
        client = get_anthropic()
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_out,
            temperature=0.1,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return {
            "blueprint": resp.content[0].text,
            "tokens": resp.usage.input_tokens + resp.usage.output_tokens,
        }
    except Exception as e:
        log.error("Claude failed: %s", e)
        return {"blueprint": f"Claude unavailable: {e}", "tokens": 0}


async def run_claude(junk_desc: str, project_type: str,
                      grok_analysis, detail_level: str,
                      conception_context: str, grok_ok: bool = True,
                      mode: str = "blueprint", research_text: str = "") -> dict:
    return await asyncio.to_thread(
        run_claude_sync, junk_desc, project_type,
        grok_analysis, detail_level, conception_context, grok_ok, mode,
        research_text
    )


def generate_schematic_sync(blueprint: str, project_type: str,
                              junk_desc: str, max_excerpt: int = 2000) -> str:
    if not ANTHROPIC_KEY:
        return ""

    system = (
        "You are a technical illustrator. Return ONLY valid SVG code.\n\n"
        "RULES: output starts with <svg ends with </svg>. Nothing else.\n"
        "Allowed: svg, rect, text, line, g, circle, ellipse, polygon, path.\n"
        "No foreignObject/image/style/script/defs. Inline styling only.\n"
        "font-family='Arial, sans-serif'. viewBox='0 0 800 550'.\n\n"
        "DRAW the project as it would LOOK assembled. Side-view.\n"
        "Use shapes for real form, not labeled rectangles.\n\n"
        "LABELS: leader lines to left/right sides. Bold 10px name + 8px gray source.\n"
        "COLORS: Structure=#2563EB, Motors=#DC2626, Electronics=#16A34A, "
        "Sensors=#9333EA, Belts=#D97706. All opacity=0.2.\n"
        "Title top-left, dimension lines, color legend bottom-right."
    )

    try:
        client = get_anthropic()
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            temperature=0.0,
            system=system,
            messages=[{
                "role": "user",
                "content": (
                    f"Draw: {project_type}\n"
                    f"Inventory: {truncate(junk_desc, 500)}\n"
                    f"Blueprint:\n{truncate(blueprint, max_excerpt)}\n"
                    f"Output ONLY <svg>...</svg>."
                ),
            }],
        )
        svg = resp.content[0].text.strip()
        start = svg.find("<svg")
        end = svg.rfind("</svg>")
        if start == -1 or end == -1:
            return ""
        svg = svg[start:end + 6].replace("```", "").replace("`", "")
        if len(svg) > 20000:
            return ""
        return svg
    except Exception as e:
        log.error("Schematic failed: %s", e)
        return ""


async def generate_schematic(blueprint: str, project_type: str,
                               junk_desc: str) -> str:
    # Smart excerpt sizing: shorter blueprints get more context, huge ones get trimmed
    bp_tokens = estimate_tokens(blueprint)
    if bp_tokens < 2000:
        first_try = min(len(blueprint), 2500)
    elif bp_tokens < 4000:
        first_try = 2000
    else:
        first_try = 1500  # Experimental blueprints are huge — keep excerpt short

    svg = await asyncio.to_thread(
        generate_schematic_sync, blueprint, project_type, junk_desc, first_try
    )
    if svg:
        return svg

    # Retry with half the excerpt
    retry_len = max(first_try // 2, 500)
    log_event("schematic_retry", first_try=first_try, retry_len=retry_len)
    return await asyncio.to_thread(
        generate_schematic_sync, blueprint, project_type, junk_desc, retry_len
    )
