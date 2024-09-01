from enum import Enum


class ReportLevel(Enum):
    pass


class Report:
    pass


class ItemReport:
    pass


class DiscordReport(Report):
    class Item(ItemReport):
        pass
    pass


class SystemReport(Report):
    class Item(ItemReport):
        pass
    pass


class EmailReport(Report):
    class Item(ItemReport):
        pass
    pass


class GoogleReport(Report):
    class Item(ItemReport):
        pass
    pass
