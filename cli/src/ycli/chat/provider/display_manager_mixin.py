from ycli.display_manager import DisplayManager

class DisplayManagerMixin:
    """Mixin class to handle display manager functionality."""

    def __init__(self):
        """Initialize with empty display manager."""
        self.display_manager = None

    def set_display_manager(self, display_manager: DisplayManager):
        """Set the display manager for the provider.

        Args:
            display_manager: Display manager instance
        """
        self.display_manager = display_manager
