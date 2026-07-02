from loguru import logger


def run_research(goal: str, model: str, depth: int, sources: int):
    logger.info(f"Starting research: goal='{goal}', model='{model}', depth={depth}, sources={sources}")


def pause_research():
    logger.info("Research paused.")


def resume_research():
    logger.info("Research resumed.")


def stop_research():
    logger.info("Research stopped.")


def load_project(name: str):
    logger.info(f"Loading project: {name}")
