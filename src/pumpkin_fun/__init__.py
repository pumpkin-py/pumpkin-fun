from pumpkin.repository import Repository, Module


def repo() -> Repository:
    repo = Repository(name="fun", package="pumpkin_fun", pip_name="pumpkin-fun")

    Module(
        "dhash",
        repo,
        "pumpkin_fun.dhash.module",
        database="pumpkin_fun.dhash.database",
    )
    Module(
        "fun",
        repo,
        "pumpkin_fun.fun.module",
    )
    Module(
        "macro",
        repo,
        "pumpkin_fun.macro.module",
        database="pumpkin_fun.macro.database",
    )
    Module(
        "names",
        repo,
        "pumpkin_fun.names.module",
        database="pumpkin_fun.names.database",
        needs_enabled={"pumpkin_boards.karma"},
    )
    Module(
        "random",
        repo,
        "pumpkin_fun.random.module",
    )
    Module(
        "seeking",
        repo,
        "pumpkin_fun.seeking.module",
        database="pumpkin_fun.seeking.database",
    )
    Module(
        "urban",
        repo,
        "pumpkin_fun.urban.module",
    )
    Module(
        "weather",
        repo,
        "pumpkin_fun.weather.module",
        database="pumpkin_fun.weather.database",
    )
    Module(
        "weeb",
        repo,
        "pumpkin_fun.weeb.module",
    )

    return repo
