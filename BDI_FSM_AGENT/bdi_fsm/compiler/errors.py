"""Compilation error — raised at any pipeline stage with position info."""


class CompileError(Exception):
    """A front/middle/back-end failure. Carries an optional line/col."""
    def __init__(self, message, line=None, col=None):
        super().__init__(message)
        self.line = line
        self.col = col
        self.message = message

# LOCATIONS - this file lives in more than one place
#
#   live:  C:\Viper\projects\BDI_FSM_AGENT
#          -> C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#   mirror: J:\ViperVault\code\projects\BDI_FSM_AGENT
#   mirror: C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#
#   live detail (freshness, git coverage): docs\LOCATIONS.md
#   regenerate: python location_stamp.py apply
# end LOCATIONS
