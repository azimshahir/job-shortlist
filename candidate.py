"""Loads and validates candidate_profile.yaml."""

import os

import yaml

import config


class ProfileError(RuntimeError):
    pass


def load_profile(path: str = None) -> dict:
    path = path or config.CANDIDATE_PROFILE_PATH
    if not os.path.exists(path):
        raise ProfileError(f"Candidate profile not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ProfileError(f"{path} did not parse as a mapping")

    sections = data.get("sections") or {}
    if not sections:
        raise ProfileError(f"{path} has no 'sections' -- nothing to rank against")

    cleaned = {}
    for name, text in sections.items():
        text = " ".join(str(text).split())
        if text:
            cleaned[name] = text
    if not cleaned:
        raise ProfileError(f"{path} sections are all empty")
    data["sections"] = cleaned
    return data


def section_items(profile: dict):
    """[(section_name, text), ...] in a stable order, so runs are deterministic."""
    return sorted(profile["sections"].items())


def must_not_claim(profile: dict) -> list:
    return [str(x) for x in (profile.get("must_not_claim") or [])]


def framing_rules(profile: dict) -> list:
    return [" ".join(str(x).split()) for x in (profile.get("framing_rules") or [])]


def pretty_section(name: str) -> str:
    return name.replace("_", " ").title()


def has_placeholders(profile: dict) -> list:
    """Return TODO_ placeholders still present. Ranking works with them;
    resume generation should not run until they are filled in."""
    found = []

    def walk(node, trail):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{trail}.{k}" if trail else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{trail}[{i}]")
        elif isinstance(node, str) and node.strip().startswith("TODO_"):
            found.append(trail)

    walk(profile, "")
    return found
