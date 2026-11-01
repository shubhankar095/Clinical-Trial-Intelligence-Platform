from dataclasses import replace

def with_changes(instance, **changes):
    return replace(instance, **changes)
