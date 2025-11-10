from __future__ import annotations

from collections import UserDict, defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable


# БАЗОВІ КЛАСИ ПОЛІВ

class Field:
    """Базове поле запису: зберігає вихідне значення і гарно друкується."""

    def __init__(self, value: Any) -> None:
        self.value = value

    def __str__(self) -> str:
        return str(self.value)


class Name(Field):
    """Поле імені (обов'язкове)."""
    pass


class Phone(Field):
    """Поле телефону з валідацією на 10 цифр."""

    def __init__(self, value: str) -> None:
        self._validate(value)
        super().__init__(value)

    @staticmethod
    def _validate(value: str) -> None:
        if not (value.isdigit() and len(value) == 10):
            raise ValueError("Phone must contain exactly 10 digits")

    def set(self, new_value: str) -> None:
        self._validate(new_value)
        self.value = new_value


class Birthday(Field):
    """
    Поле дня народження.
    Формат введення: DD.MM.YYYY
    Усередині зберігаємо datetime.date, а __str__ — виводить DD.MM.YYYY.
    """

    def __init__(self, value: str) -> None:
        try:
            dt = datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError as exc:
            raise ValueError("Invalid date format. Use DD.MM.YYYY") from exc
        super().__init__(dt)

    @property
    def date(self) -> date:
        return self.value  # type: ignore[return-value]

    def __str__(self) -> str:
        return self.date.strftime("%d.%m.%Y")


# ------------- ЗАПИС КОНТАКТУ -------------

class Record:
    """Один контакт: ім'я + список телефонів + (необов'язковий) день народження."""

    def __init__(self, name: str) -> None:
        self.name: Name = Name(name)
        self.phones: List[Phone] = []
        self.birthday: Optional[Birthday] = None

    # ---- телефони ----
    def add_phone(self, phone: str) -> None:
        self.phones.append(Phone(phone))

    def remove_phone(self, phone: str) -> bool:
        for i, ph in enumerate(self.phones):
            if ph.value == phone:
                self.phones.pop(i)
                return True
        return False

    def edit_phone(self, old_phone: str, new_phone: str) -> None:
        for ph in self.phones:
            if ph.value == old_phone:
                ph.set(new_phone)
                return
        raise ValueError("Old phone not found")

    def find_phone(self, phone: str) -> Optional[str]:
        for ph in self.phones:
            if ph.value == phone:
                return ph.value
        return None

    # ---- день народження ----
    def add_birthday(self, birthday_str: str) -> None:
        self.birthday = Birthday(birthday_str)

    def __str__(self) -> str:
        phones = "; ".join(p.value for p in self.phones) if self.phones else "—"
        birthday_str = str(self.birthday) if self.birthday else "—"
        return f"Contact name: {self.name.value}, phones: {phones}, birthday: {birthday_str}"


# ------------- АДРЕСНА КНИГА --------------

class AddressBook(UserDict):
    """Книга контактів (словник name -> Record)."""

    def add_record(self, record: Record) -> None:
        self.data[record.name.value] = record

    def find(self, name: str) -> Optional[Record]:
        return self.data.get(name)

    def delete(self, name: str) -> None:
        self.data.pop(name, None)

    # ---- дні народження наступного тижня ----
    def get_upcoming_birthdays(self) -> Dict[date, List[str]]:
        """
        Повертає мапу {дата-привітання: [імена, ...]} для контактів,
        у яких ДН протягом наступних 7 днів. Привітання, що випадають на
        суботу/неділю, переносяться на понеділок.
        """
        today = date.today()
        end = today + timedelta(days=7)
        result: Dict[date, List[str]] = defaultdict(list)

        for rec in self.data.values():
            if not rec.birthday:
                continue

            birthday_this_year = rec.birthday.date.replace(year=today.year)

            # якщо вже минув цього року — дивимось наступний
            if birthday_this_year < today:
                birthday_this_year = rec.birthday.date.replace(year=today.year + 1)

            if today <= birthday_this_year <= end:
                congratulation_day = birthday_this_year
                # перенесення з вихідних на понеділок
                if congratulation_day.weekday() == 5:  # Saturday
                    congratulation_day += timedelta(days=2)
                elif congratulation_day.weekday() == 6:  # Sunday
                    congratulation_day += timedelta(days=1)

                result[congratulation_day].append(rec.name.value)

        # впорядкуємо за датою
        return dict(sorted(result.items(), key=lambda x: x[0]))


#  ДОПОМІЖНЕ ДЛЯ CLI

def parse_input(user_input: str) -> Tuple[str, List[str]]:
    """Розбирає введений рядок на команду та аргументи."""
    user_input = user_input.strip()
    if not user_input:
        return "", []
    parts = user_input.split()
    return parts[0].lower(), parts[1:]


def help_message() -> str:
    return (
        "Commands:\n"
        "  hello                       - Greet\n"
        "  add [name] [phone]          - Add new contact or phone to existing\n"
        "  change [name] [old] [new]   - Change existing phone\n"
        "  phone [name]                - Show phones by name\n"
        "  all                         - Show all contacts\n"
        "  add-birthday [name] [DD.MM.YYYY]   - Add birthday to contact\n"
        "  show-birthday [name]        - Show contact birthday\n"
        "  birthdays                   - Show upcoming birthdays (7 days)\n"
        "  help / ?                    - This help\n"
        "  exit / close                - Exit program"
    )


# декоратор обробки помилок

Handler = Callable[[List[str], AddressBook], str]


def input_error(func: Handler) -> Handler:
    def wrapper(args: List[str], book: AddressBook) -> str:  # type: ignore[override]
        try:
            return func(args, book)
        except ValueError as e:
            return str(e)
        except KeyError:
            return "Contact not found."
        except IndexError:
            return "Not enough arguments. Type 'help' to see usage."
        except Exception as e:
            # безпечне повідомлення на будь-що інше
            return f"Error: {e}"

    return wrapper  # type: ignore[return-value]


# ОБРОБНИКИ КОМАНД

@input_error
def add_contact(args: List[str], book: AddressBook) -> str:
    name, phone, *_ = args
    record = book.find(name)
    msg = "Contact updated."
    if record is None:
        record = Record(name)
        book.add_record(record)
        msg = "Contact added."
    record.add_phone(phone)
    return msg


@input_error
def change_contact(args: List[str], book: AddressBook) -> str:
    name, old_phone, new_phone, *_ = args
    record = book.find(name)
    if record is None:
        raise KeyError
    record.edit_phone(old_phone, new_phone)
    return "Phone updated."


@input_error
def show_phones(args: List[str], book: AddressBook) -> str:
    name, *_ = args
    record = book.find(name)
    if record is None:
        raise KeyError
    phones = ", ".join(p.value for p in record.phones) if record.phones else "—"
    return f"{name}: {phones}"


def show_all(book: AddressBook) -> str:
    if not book.data:
        return "No contacts yet."
    lines = [str(rec) for rec in book.data.values()]
    return "All contacts:\n" + "\n".join(lines)


@input_error
def add_birthday(args: List[str], book: AddressBook) -> str:
    name, birthday_str, *_ = args
    record = book.find(name)
    if record is None:
        # створюємо контакт, якщо не існує
        record = Record(name)
        book.add_record(record)

    record.add_birthday(birthday_str)
    return "Birthday added."


@input_error
def show_birthday(args: List[str], book: AddressBook) -> str:
    name, *_ = args
    record = book.find(name)
    if record is None or record.birthday is None:
        return "No birthday set."
    return f"{name}: {record.birthday}"


@input_error
def birthdays(_args: List[str], book: AddressBook) -> str:
    upcoming = book.get_upcoming_birthdays()
    if not upcoming:
        return "No birthdays in the next 7 days."
    lines: List[str] = []
    for day, names in upcoming.items():
        lines.append(f"{day.strftime('%d.%m.%Y')}: {', '.join(names)}")
    return "Upcoming birthdays:\n" + "\n".join(lines)


# ГОЛОВНИЙ ЦИКЛ

def main() -> None:
    book = AddressBook()
    print("Welcome to the assistant bot! Type 'help' for commands.")

    while True:
        user_input = input("Enter a command: ")
        command, args = parse_input(user_input)

        if command in ("close", "exit"):
            print("Good bye!")
            break
        elif command in ("help", "?"):
            print(help_message())
        elif command == "hello":
            print("How can I help you?")
        elif command == "add":
            print(add_contact(args, book))
        elif command == "change":
            print(change_contact(args, book))
        elif command == "phone":
            print(show_phones(args, book))
        elif command == "all":
            print(show_all(book))
        elif command == "add-birthday":
            print(add_birthday(args, book))
        elif command == "show-birthday":
            print(show_birthday(args, book))
        elif command == "birthdays":
            print(birthdays(args, book))
        else:
            print("Invalid command. Type 'help' to see available commands.")


if __name__ == "__main__":
    main()
