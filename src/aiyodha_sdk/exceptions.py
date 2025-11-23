class BudgetExceededError(Exception):
    """Raised when the agent has exceeded its budget or has been killed."""
    pass

class CircuitBreakerTrippedError(Exception):
    """Raised when Circuit Breaker is tripped due to Policy Engine failures"""
    pass
