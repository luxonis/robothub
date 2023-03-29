import warnings

import robothub

__all__ = ['RobotHubApplication']


class RobotHubApplication(robothub.RobotHubApplication):
    """
    Wrapper for robothub.RobotHubApplication to add DepthAI specific functionality.
    """

    def __init__(self):
        warnings.warn('RobotHubApplication is deprecated, use robothub.RobotHubApplication instead.',
                      DeprecationWarning)
        super().__init__()
