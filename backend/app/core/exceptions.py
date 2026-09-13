class AutoDisclosureError(Exception):
    """Base class for controlled errors safe to map to API messages."""


class InvalidRepositoryUrlError(AutoDisclosureError):
    pass


class RepositoryNotFoundError(AutoDisclosureError):
    pass


class GitUnavailableError(AutoDisclosureError):
    pass


class RepositoryCloneError(AutoDisclosureError):
    pass


class RepositoryTooLargeError(AutoDisclosureError):
    pass


class UnsafePathError(AutoDisclosureError):
    pass


class FileTooLargeError(AutoDisclosureError):
    pass


class BinaryFileError(AutoDisclosureError):
    pass


class BedrockAuthenticationError(AutoDisclosureError):
    pass


class BedrockAccessDeniedError(AutoDisclosureError):
    pass


class BedrockModelUnavailableError(AutoDisclosureError):
    pass


class RepositoryAgentError(AutoDisclosureError):
    pass


class FindingNotFoundError(AutoDisclosureError):
    pass


class FindingNotRemediableError(AutoDisclosureError):
    pass


class RemediationContextError(AutoDisclosureError):
    pass


class RemediationAgentError(AutoDisclosureError):
    pass


class InvalidPatchError(AutoDisclosureError):
    pass


class PatchTooLargeError(InvalidPatchError):
    pass


class PatchNotFoundError(AutoDisclosureError):
    pass


class InvalidPatchTransitionError(AutoDisclosureError):
    pass


class PatchNotApprovedError(AutoDisclosureError):
    pass


class PatchAlreadyAppliedError(AutoDisclosureError):
    pass


class PatchApplicationError(AutoDisclosureError):
    pass


class PatchRollbackError(PatchApplicationError):
    pass


class PatchVerificationError(AutoDisclosureError):
    pass
