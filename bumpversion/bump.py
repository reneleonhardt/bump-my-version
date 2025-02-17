"""Version changing methods."""
import logging
import shlex
from pathlib import Path
from typing import TYPE_CHECKING, ChainMap, List, Optional

if TYPE_CHECKING:  # pragma: no-coverage
    from bumpversion.files import ConfiguredFile
    from bumpversion.version_part import Version

from bumpversion.config import Config, update_config_file
from bumpversion.exceptions import ConfigurationError
from bumpversion.utils import get_context, key_val_string

logger = logging.getLogger("bumpversion")


def get_next_version(
    current_version: "Version", config: Config, version_part: Optional[str], new_version: Optional[str]
) -> "Version":
    """
    Bump the version_part to the next value.

    Args:
        current_version: The current version
        config: The current configuration
        version_part: Optional part of the version to bump
        new_version: Optional specific version to bump to

    Returns:
        The new version

    Raises:
        ConfigurationError: If it can't generate the next version.
    """
    if new_version:
        next_version = config.version_config.parse(new_version)
    elif version_part:
        logger.info("Attempting to increment part '%s'", version_part)
        next_version = current_version.bump(version_part, config.version_config.order)
    else:
        raise ConfigurationError("Unable to get the next version.")

    logger.info("Values are now: %s", key_val_string(next_version.values))
    return next_version


def do_bump(
    version_part: Optional[str],
    new_version: Optional[str],
    config: Config,
    config_file: Optional[Path] = None,
    dry_run: bool = False,
) -> None:
    """
    Bump the version_part to the next value or set the version to new_version.

    Args:
        version_part: The version part to bump
        new_version: The explicit version to set
        config: The configuration to use
        config_file: The configuration file to update
        dry_run: True if the operation should be a dry run
    """
    from bumpversion.files import modify_files, resolve_file_config

    ctx = get_context(config)
    version = config.version_config.parse(config.current_version)
    next_version = get_next_version(version, config, version_part, new_version)
    next_version_str = config.version_config.serialize(next_version, ctx)
    logger.info("New version will be '%s'", next_version_str)

    if config.current_version == next_version_str:
        logger.info("Version is already '%s'", next_version_str)
        return

    if dry_run:
        logger.info("Dry run active, won't touch any files.")

    ctx = get_context(config, version, next_version)

    configured_files = resolve_file_config(config.files_to_modify, config.version_config)
    modify_files(configured_files, version, next_version, ctx, dry_run)
    update_config_file(config_file, config.current_version, next_version_str, dry_run)

    ctx = get_context(config, version, next_version)
    ctx["new_version"] = next_version_str
    commit_and_tag(config, config_file, configured_files, ctx, dry_run)


def commit_and_tag(
    config: Config,
    config_file: Optional[Path],
    configured_files: List["ConfiguredFile"],
    ctx: ChainMap,
    dry_run: bool = False,
) -> None:
    """
    Commit and tag the changes, if a tool is configured.

    Args:
        config: The configuration
        config_file: The configuration file to include in the commit, if it exists
        configured_files: A list of files to commit
        ctx: The context used to render the tag and tag message
        dry_run: True if the operation should be a dry run
    """
    if not config.scm_info.tool:
        return

    extra_args = shlex.split(config.commit_args) if config.commit_args else []

    commit_files = {f.path for f in configured_files}
    if config_file:
        commit_files |= {str(config_file)}

    config.scm_info.tool.commit_to_scm(list(commit_files), config, ctx, extra_args, dry_run)
    config.scm_info.tool.tag_in_scm(config, ctx, dry_run)
