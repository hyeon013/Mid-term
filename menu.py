"""메뉴 추천, 메뉴 관리, 식사 기록 통계를 제공하는 GUI 프로그램."""

from __future__ import annotations

import json
import random
import csv
import shutil
import webbrowser
import zipfile
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from uuid import uuid4
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


BASE_DIR = Path(__file__).resolve().parent
MENU_FILE = BASE_DIR / "menus.json"
HISTORY_FILE = BASE_DIR / "meal_history.json"
FAVORITES_FILE = BASE_DIR / "favorites.json"
PREFERENCES_FILE = BASE_DIR / "preferences.json"
MENU_IMAGE_DIR = BASE_DIR / "menu_images"
MENU_IMAGE_EXTENSIONS = {".gif", ".png"}
SPICE_LABELS = {0: "안 매움", 1: "약간 매움", 2: "매움", 3: "아주 매움"}
STAPLE_CHOICES = ("면", "빵", "밥", "기타")
TEMPERATURE_CHOICES = ("따뜻한", "차가운")
RECENT_MEAL_DAYS = 7
DIET_LABELS = {"vegetarian": "채식", "vegan": "비건"}
MEAL_CATEGORIES = ("간편식", "야식", "식사", "간식")
TASTE_LABELS = {
    "salty": "짠",
    "sweet": "달달한",
    "spicy": "매운",
    "mild": "담백한",
}


def _positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _resolve_menu_image(image: Any) -> Path | None:
    if not isinstance(image, str) or not image.strip():
        return None
    relative_path = Path(image)
    if relative_path.is_absolute():
        return None
    try:
        path = (BASE_DIR / relative_path).resolve()
        path.relative_to(MENU_IMAGE_DIR.resolve())
    except (OSError, RuntimeError, ValueError):
        return None
    if path.suffix.casefold() not in MENU_IMAGE_EXTENSIONS or not path.is_file():
        return None
    return path


def load_menus(
    path: Path = MENU_FILE,
    *,
    on_warning: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """메뉴 카탈로그를 읽고 필수 데이터가 유효한 항목만 반환한다."""
    report = on_warning or print
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        report(f"메뉴 데이터 파일을 찾을 수 없습니다: {path}")
        return []
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        report(f"메뉴 데이터 파일을 읽을 수 없습니다: {error}")
        return []

    if not isinstance(data, list):
        report("메뉴 데이터 형식이 올바르지 않습니다. 최상위 값은 목록이어야 합니다.")
        return []

    valid_menus: list[dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            report(f"{index}번째 메뉴를 건너뜁니다: 항목이 객체가 아닙니다.")
            continue

        name = item.get("name")
        category = item.get("category")
        meal_type = item.get("meal_type")
        price = item.get("price")
        spice_level = item.get("spice_level")
        staple = item.get("staple")
        has_soup = item.get("has_soup")
        temperature = item.get("temperature")
        tastes = item.get("tastes")
        diet_tags = item.get("diet_tags", [])
        meal_categories = item.get("meal_categories", [])
        image = item.get("image", "")
        if not isinstance(image, str) or (
            image and _resolve_menu_image(image) is None
        ):
            report(
                f"{index}번째 메뉴 사진 파일을 찾을 수 없거나 "
                "경로가 올바르지 않습니다."
            )
            image = ""
        if not isinstance(name, str) or not name.strip():
            reason = "이름 누락"
        elif not isinstance(category, str) or not category.strip():
            reason = "음식 종류 누락"
        elif not isinstance(meal_type, str) or not meal_type.strip():
            reason = "식사 방식 누락"
        elif not _positive_integer(price):
            reason = "가격이 없거나 올바른 양의 정수가 아님"
        elif (
            not isinstance(spice_level, int)
            or isinstance(spice_level, bool)
            or spice_level not in SPICE_LABELS
        ):
            reason = "맵기 단계는 0~3의 정수여야 함"
        elif staple not in STAPLE_CHOICES:
            reason = "주식은 면, 빵, 밥, 기타 중 하나여야 함"
        elif not isinstance(has_soup, bool):
            reason = "국물 유무는 참/거짓 값이어야 함"
        elif temperature not in TEMPERATURE_CHOICES:
            reason = "온도는 따뜻한 또는 차가운 중 하나여야 함"
        elif (
            not isinstance(tastes, list)
            or any(
                not isinstance(taste, str) or taste not in TASTE_LABELS
                for taste in tastes
            )
            or len(set(tastes)) != len(tastes)
        ):
            reason = "맛 특징은 짠, 달달한, 매운, 담백한 목록이어야 함"
        elif (
            not isinstance(diet_tags, list)
            or any(
                not isinstance(tag, str) or tag not in DIET_LABELS
                for tag in diet_tags
            )
            or len(set(diet_tags)) != len(diet_tags)
        ):
            reason = "식단 태그는 채식 또는 비건 목록이어야 함"
        elif (
            not isinstance(meal_categories, list)
            or any(
                not isinstance(category_name, str)
                or category_name not in MEAL_CATEGORIES
                for category_name in meal_categories
            )
            or len(set(meal_categories)) != len(meal_categories)
        ):
            reason = "메뉴 구분은 간편식, 야식, 식사, 간식 목록이어야 함"
        else:
            valid_menus.append(
                {
                    "name": name.strip(),
                    "category": category.strip(),
                    "meal_type": meal_type.strip(),
                    "price": price,
                    "spice_level": spice_level,
                    "staple": staple,
                    "has_soup": has_soup,
                    "temperature": temperature,
                    "tastes": tastes.copy(),
                    "diet_tags": diet_tags.copy(),
                    "meal_categories": meal_categories.copy(),
                    "image": image.strip(),
                    "description": (
                        item.get("description", "").strip()
                        if isinstance(item.get("description", ""), str)
                        else ""
                    ),
                }
            )
            continue
        report(f"{index}번째 메뉴를 건너뜁니다: {reason}.")

    if not valid_menus:
        report("추천 가능한 메뉴 데이터가 없습니다.")
    return valid_menus


def save_menus(
    menus: list[dict[str, Any]],
    path: Path = MENU_FILE,
    *,
    on_error: Callable[[str], None] | None = None,
) -> bool:
    """메뉴 카탈로그를 임시 파일에 쓴 뒤 교체한다."""
    temporary_path = path.with_name(f"{path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(menus, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temporary_path.replace(path)
    except OSError as error:
        message = f"메뉴 데이터를 저장할 수 없습니다: {error}"
        if on_error is not None:
            on_error(message)
        else:
            print(message)
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def load_favorites(
    menus: list[dict[str, Any]],
    path: Path = FAVORITES_FILE,
    *,
    on_warning: Callable[[str], None] | None = None,
) -> set[str]:
    """저장된 즐겨찾기 중 현재 카탈로그에 존재하는 이름만 반환한다."""
    report = on_warning or print
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return set()
    except (OSError, json.JSONDecodeError) as error:
        report(f"즐겨찾기를 읽을 수 없습니다: {error}")
        return set()

    if not isinstance(data, list) or any(
        not isinstance(name, str) for name in data
    ):
        report("즐겨찾기 데이터 형식이 올바르지 않아 불러오지 못했습니다.")
        return set()
    menu_names = {menu["name"] for menu in menus}
    favorites = set(data) & menu_names
    if len(favorites) != len(set(data)):
        report("메뉴 목록에 없는 즐겨찾기는 제외했습니다.")
    return favorites


def save_favorites(
    favorites: set[str],
    path: Path = FAVORITES_FILE,
    *,
    on_error: Callable[[str], None] | None = None,
) -> bool:
    """즐겨찾기를 임시 파일에 쓴 뒤 교체한다."""
    temporary_path = path.with_name(f"{path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(sorted(favorites), file, ensure_ascii=False, indent=2)
            file.write("\n")
        temporary_path.replace(path)
    except OSError as error:
        message = f"즐겨찾기를 저장할 수 없습니다: {error}"
        if on_error is not None:
            on_error(message)
        else:
            print(message)
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def _valid_history_entry(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    name = entry.get("name")
    category = entry.get("category")
    amount = entry.get("amount")
    recorded_on = entry.get("date")
    if (
        not isinstance(name, str)
        or not name.strip()
        or not isinstance(category, str)
        or not category.strip()
        or not _positive_integer(amount)
        or not isinstance(recorded_on, str)
    ):
        return False
    try:
        date.fromisoformat(recorded_on)
    except ValueError:
        return False
    return True


def load_history(
    path: Path = HISTORY_FILE,
    *,
    on_warning: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """식사 기록을 읽으며 잘못된 기록은 사용자에게 알리고 제외한다."""
    report = on_warning or print
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as error:
        report(f"식사 기록 파일을 읽을 수 없습니다: {error}")
        return []

    if not isinstance(data, list):
        report("식사 기록 형식이 올바르지 않습니다. 기록을 불러오지 못했습니다.")
        return []

    entries: list[dict[str, Any]] = []
    invalid_count = 0
    invalid_memo_count = 0
    for entry in data:
        if not _valid_history_entry(entry):
            invalid_count += 1
            continue
        normalized_entry = entry.copy()
        for key in ("location", "companions", "note"):
            value = normalized_entry.get(key, "")
            if not isinstance(value, str):
                normalized_entry[key] = ""
                invalid_memo_count += 1
            else:
                normalized_entry[key] = value
        want_again = normalized_entry.get("want_again", False)
        if not isinstance(want_again, bool):
            normalized_entry["want_again"] = False
            invalid_memo_count += 1
        else:
            normalized_entry["want_again"] = want_again
        entries.append(normalized_entry)
    if invalid_count:
        report(f"올바르지 않은 식사 기록 {invalid_count}건을 제외했습니다.")
    if invalid_memo_count:
        report(f"형식이 잘못된 식사 메모 {invalid_memo_count}개를 비우거나 기본값으로 처리했습니다.")
    return entries


def save_history(
    entries: list[dict[str, Any]],
    path: Path = HISTORY_FILE,
    *,
    on_error: Callable[[str], None] | None = None,
) -> bool:
    """기록을 임시 파일에 쓴 뒤 교체하여 저장 도중 파일 손상을 줄인다."""
    temporary_path = path.with_name(f"{path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(entries, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temporary_path.replace(path)
    except OSError as error:
        message = f"식사 기록을 저장할 수 없습니다: {error}"
        if on_error is not None:
            on_error(message)
        else:
            print(message)
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True


def filter_menus(
    menus: list[dict[str, Any]],
    budget: int | None = None,
    category: str | None = None,
    max_spice: int | None = None,
    meal_type: str | None = None,
    staple: str | None = None,
    has_soup: bool | None = None,
    temperature: str | None = None,
    tastes: list[str] | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    diet_tag: str | None = None,
    excluded_names: set[str] | None = None,
    meal_category: str | None = None,
) -> list[dict[str, Any]]:
    """설정한 조건을 모두 만족하는 메뉴만 반환한다."""
    return [
        menu
        for menu in menus
        if (budget is None or menu["price"] <= budget)
        and (min_price is None or menu["price"] >= min_price)
        and (max_price is None or menu["price"] <= max_price)
        and (excluded_names is None or menu["name"] not in excluded_names)
        and (
            diet_tag is None
            or diet_tag in menu["diet_tags"]
            or (diet_tag == "vegetarian" and "vegan" in menu["diet_tags"])
        )
        and (category is None or menu["category"] == category)
        and (max_spice is None or menu["spice_level"] <= max_spice)
        and (meal_type is None or menu["meal_type"] == meal_type)
        and (staple is None or menu["staple"] == staple)
        and (has_soup is None or menu["has_soup"] is has_soup)
        and (temperature is None or menu["temperature"] == temperature)
        and all(taste in menu["tastes"] for taste in (tastes or []))
        and (
            meal_category is None
            or meal_category in menu.get("meal_categories", [])
        )
    ]


class MenuApp:
    """메뉴 추천과 식사 기록을 다루는 Tkinter 애플리케이션."""

    COLORS = {
        "background": "#FFF8F1",
        "surface": "#FFFFFF",
        "surface_alt": "#FFF1E5",
        "primary": "#D96B3B",
        "primary_dark": "#B84F28",
        "text": "#34251F",
        "muted": "#806F65",
        "border": "#EADFD5",
        "selection": "#FBE1D1",
    }

    def __init__(
        self,
        root: tk.Tk,
        menus: list[dict[str, Any]],
        history: list[dict[str, Any]],
        favorites: set[str] | None = None,
    ) -> None:
        self.root = root
        self.menus = menus
        self.history = history
        self.favorites = favorites if favorites is not None else set()
        self.visible_menus: list[dict[str, Any]] = []
        self.visible_favorites: list[dict[str, Any]] = []
        self.root.title("오늘 뭐 먹지? 메뉴 추천")
        self.root.geometry("1160x900")
        self.root.minsize(900, 700)
        self.root.configure(background=self.COLORS["background"])

        self._configure_styles()

        self._build_layout()
        self._show_results(self.menus, f"등록된 메뉴 {len(self.menus)}개")
        self._refresh_menu_lists()
        self._refresh_history()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        colors = self.COLORS
        style.configure(".", font=("맑은 고딕", 10), foreground=colors["text"])
        style.configure("TFrame", background=colors["background"])
        style.configure("App.TFrame", background=colors["background"])
        style.configure("Card.TFrame", background=colors["surface"])
        style.configure("Info.TFrame", background=colors["surface_alt"])
        style.configure("Hero.TFrame", background=colors["primary"])
        style.configure("TLabel", background=colors["background"], foreground=colors["text"])
        style.configure(
            "Title.TLabel",
            background=colors["primary"],
            foreground="#FFFFFF",
            font=("맑은 고딕", 23, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=colors["primary"],
            foreground="#FFF4EC",
            font=("맑은 고딕", 10),
        )
        style.configure(
            "Eyebrow.TLabel",
            background=colors["primary"],
            foreground="#FFE1CC",
            font=("맑은 고딕", 9, "bold"),
        )
        style.configure(
            "Count.TLabel",
            background="#C85A31",
            foreground="#FFFFFF",
            font=("맑은 고딕", 10, "bold"),
            padding=(12, 8),
        )
        style.configure(
            "Section.TLabel",
            background=colors["background"],
            foreground=colors["text"],
            font=("맑은 고딕", 12, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=colors["background"],
            foreground=colors["muted"],
        )
        style.configure(
            "CardTitle.TLabel",
            background=colors["surface_alt"],
            foreground=colors["primary_dark"],
            font=("맑은 고딕", 10, "bold"),
        )
        style.configure(
            "CardBody.TLabel",
            background=colors["surface_alt"],
            foreground=colors["text"],
            font=("맑은 고딕", 10),
        )
        style.configure(
            "Metric.TFrame",
            background=colors["surface"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "MetricTitle.TLabel",
            background=colors["surface"],
            foreground=colors["muted"],
            font=("맑은 고딕", 9),
        )
        style.configure(
            "MetricValue.TLabel",
            background=colors["surface"],
            foreground=colors["primary_dark"],
            font=("맑은 고딕", 16, "bold"),
        )
        style.configure(
            "TLabelframe",
            background=colors["background"],
            bordercolor=colors["border"],
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "TLabelframe.Label",
            background=colors["background"],
            foreground=colors["primary_dark"],
            font=("맑은 고딕", 11, "bold"),
        )
        style.configure(
            "TNotebook",
            background=colors["background"],
            borderwidth=0,
            tabmargins=(0, 0, 0, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background=colors["surface_alt"],
            foreground=colors["muted"],
            padding=(18, 10),
            font=("맑은 고딕", 10, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", colors["surface"])],
            foreground=[("selected", colors["primary_dark"])],
        )
        style.configure(
            "TButton",
            background=colors["surface"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            padding=(12, 8),
            font=("맑은 고딕", 9, "bold"),
        )
        style.map(
            "TButton",
            background=[("active", colors["surface_alt"]), ("pressed", "#F3DDCC")],
        )
        style.configure(
            "Primary.TButton",
            background=colors["primary"],
            foreground="#FFFFFF",
            bordercolor=colors["primary"],
            padding=(14, 9),
            font=("맑은 고딕", 9, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[
                ("active", colors["primary_dark"]),
                ("pressed", colors["primary_dark"]),
            ],
            foreground=[("active", "#FFFFFF"), ("pressed", "#FFFFFF")],
        )
        style.configure(
            "TEntry",
            fieldbackground=colors["surface"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            padding=7,
        )
        style.configure(
            "TCombobox",
            fieldbackground=colors["surface"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            padding=6,
            arrowsize=13,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", colors["surface"])],
            selectbackground=[("readonly", colors["surface"])],
            selectforeground=[("readonly", colors["text"])],
        )
        style.configure(
            "TCheckbutton",
            background=colors["background"],
            foreground=colors["text"],
        )
        style.map("TCheckbutton", background=[("active", colors["background"])])
        style.configure(
            "Treeview",
            background=colors["surface"],
            fieldbackground=colors["surface"],
            foreground=colors["text"],
            rowheight=34,
            font=("맑은 고딕", 9),
            bordercolor=colors["border"],
            borderwidth=1,
        )
        style.configure(
            "Treeview.Heading",
            background=colors["surface_alt"],
            foreground=colors["primary_dark"],
            font=("맑은 고딕", 9, "bold"),
            padding=(7, 9),
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", colors["selection"])],
            foreground=[("selected", colors["text"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=colors["surface_alt"],
            troughcolor=colors["background"],
            bordercolor=colors["background"],
            arrowsize=12,
        )

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=(24, 20), style="App.TFrame")
        container.pack(fill="both", expand=True)
        hero = ttk.Frame(container, padding=(22, 18), style="Hero.TFrame")
        hero.pack(fill="x", pady=(0, 18))
        hero_text = ttk.Frame(hero, style="Hero.TFrame")
        hero_text.pack(side="left", fill="x", expand=True)
        ttk.Label(hero_text, text="오늘의 한 끼", style="Eyebrow.TLabel").pack(
            anchor="w", pady=(0, 4)
        )
        ttk.Label(hero_text, text="오늘 뭐 먹지?", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            hero_text,
            text="입맛에 딱 맞는 메뉴를 골라보세요.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(5, 0))
        self.menu_count_label = ttk.Label(
            hero, text=f"메뉴 {len(self.menus)}가지", style="Count.TLabel"
        )
        self.menu_count_label.pack(side="right", anchor="center", padx=(16, 2))

        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True)
        recommend_tab = ttk.Frame(notebook, padding=18, style="App.TFrame")
        nearby_tab = ttk.Frame(notebook, padding=18, style="App.TFrame")
        history_tab = ttk.Frame(notebook, padding=18, style="App.TFrame")
        favorites_tab = ttk.Frame(notebook, padding=18, style="App.TFrame")
        manage_tab = ttk.Frame(notebook, padding=18, style="App.TFrame")
        self.main_notebook = notebook
        self.recommend_tab = recommend_tab
        notebook.add(recommend_tab, text="메뉴 추천")
        notebook.add(nearby_tab, text="주변 식당")
        notebook.add(history_tab, text="식사 기록 · 통계")
        notebook.add(favorites_tab, text="즐겨찾기")
        notebook.add(manage_tab, text="메뉴 관리")
        self._build_recommend_tab(recommend_tab)
        self._build_nearby_tab(nearby_tab)
        self._build_history_tab(history_tab)
        self._build_favorites_tab(favorites_tab)
        self._build_manage_tab(manage_tab)

    def _build_nearby_tab(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, padding=(24, 22), style="Info.TFrame")
        card.pack(fill="x", pady=(0, 12))
        ttk.Label(
            card, text="지금 주변 식당 찾기", style="Section.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            card,
            text=(
                "Google 지도를 열어 현재 위치 주변의 식당을 검색합니다. "
                "위치 접근은 Google 지도와 브라우저가 처리하며, "
                "이 프로그램은 현재 위치를 읽거나 저장하지 않습니다."
            ),
            style="CardBody.TLabel",
            wraplength=850,
            justify="left",
        ).pack(anchor="w", pady=(8, 14))
        ttk.Label(card, text="음식 종류", style="CardTitle.TLabel").pack(
            anchor="w", pady=(0, 5)
        )
        self.restaurant_category_var = tk.StringVar(value="전체")
        self.restaurant_category_box = ttk.Combobox(
            card,
            textvariable=self.restaurant_category_var,
            values=("전체", *sorted({item["category"] for item in self.menus})),
            state="readonly",
            width=24,
        )
        self.restaurant_category_box.pack(anchor="w", pady=(0, 12))
        ttk.Button(
            card,
            text="선택한 종류 주변 식당 찾기",
            style="Primary.TButton",
            command=self._open_nearby_restaurants,
        ).pack(anchor="w")
        ttk.Label(
            parent,
            text="브라우저 위치 권한을 허용하거나 지도에서 위치를 직접 선택하세요.",
            style="Muted.TLabel",
            wraplength=850,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

    def _open_nearby_restaurants(self) -> None:
        category = self.restaurant_category_var.get()
        search_term = "restaurants near me"
        if category != "전체":
            search_term = f"{category} restaurants near me"
        query = urlencode({"api": "1", "query": search_term})
        url = f"https://www.google.com/maps/search/?{query}"
        try:
            opened = webbrowser.open_new_tab(url)
        except webbrowser.Error as error:
            messagebox.showerror(
                "지도 열기 오류",
                f"기본 브라우저에서 Google 지도를 열지 못했습니다: {error}",
                parent=self.root,
            )
            return
        if not opened:
            messagebox.showerror(
                "지도 열기 오류",
                "기본 브라우저를 열지 못했습니다. 브라우저 설정을 확인해 주세요.",
                parent=self.root,
            )

    def _build_recommend_tab(self, parent: ttk.Frame) -> None:
        filters = ttk.LabelFrame(
            parent, text="  입맛에 맞게 골라보기  ", padding=(14, 12)
        )
        filters.pack(fill="x")

        categories = sorted({menu["category"] for menu in self.menus})
        meal_types = sorted({menu["meal_type"] for menu in self.menus})
        self.min_price_var = tk.StringVar()
        self.max_price_var = tk.StringVar()
        self.category_var = tk.StringVar(value="상관없음")
        self.spice_var = tk.StringVar(value="상관없음")
        self.meal_type_var = tk.StringVar(value="상관없음")
        self.meal_category_var = tk.StringVar(value="상관없음")
        self.staple_var = tk.StringVar(value="상관없음")
        self.soup_var = tk.StringVar(value="상관없음")
        self.temperature_var = tk.StringVar(value="상관없음")
        self.diet_var = tk.StringVar(value="상관없음")
        self.exclude_recent_var = tk.BooleanVar(value=True)
        self.filter_taste_vars = {
            taste: tk.BooleanVar(value=False) for taste in TASTE_LABELS
        }

        fields: tuple[
            tuple[str, tk.StringVar, tuple[str, ...] | None], ...
        ] = (
            ("최소 가격 (원)", self.min_price_var, None),
            ("최대 가격 (원)", self.max_price_var, None),
            ("음식 종류", self.category_var, ("상관없음", *categories)),
            ("맵기 상한", self.spice_var, ("상관없음", *SPICE_LABELS.values())),
            ("식사 방식", self.meal_type_var, ("상관없음", *meal_types)),
            (
                "메뉴 구분",
                self.meal_category_var,
                ("상관없음", *MEAL_CATEGORIES),
            ),
            ("주식", self.staple_var, ("상관없음", *STAPLE_CHOICES)),
            ("국물", self.soup_var, ("상관없음", "국물 있음", "국물 없음")),
            (
                "온도",
                self.temperature_var,
                ("상관없음", *TEMPERATURE_CHOICES),
            ),
            (
                "식단",
                self.diet_var,
                ("상관없음", *DIET_LABELS.values()),
            ),
        )
        for column, (label, variable, choices) in enumerate(fields):
            field = ttk.Frame(filters)
            row, grid_column = divmod(column, 4)
            field.grid(row=row, column=grid_column, sticky="ew", padx=5, pady=3)
            ttk.Label(field, text=label).pack(anchor="w", pady=(0, 5))
            if choices is None:
                widget = ttk.Entry(field, textvariable=variable, width=17)
            else:
                widget = ttk.Combobox(
                    field,
                    textvariable=variable,
                    values=choices,
                    state="readonly",
                    width=15,
                )
            widget.pack(fill="x")
            if label == "음식 종류":
                self.category_box = widget
            elif label == "식사 방식":
                self.meal_type_box = widget
            filters.columnconfigure(grid_column, weight=1)
        taste_frame = ttk.Frame(filters, style="App.TFrame")
        taste_row = (len(fields) + 3) // 4
        taste_frame.grid(
            row=taste_row, column=0, columnspan=4, sticky="w", padx=5, pady=5
        )
        ttk.Label(
            taste_frame, text="맛 특징", style="Section.TLabel"
        ).pack(side="left", padx=(0, 10))
        for taste, label in TASTE_LABELS.items():
            ttk.Checkbutton(
                taste_frame,
                text=label,
                variable=self.filter_taste_vars[taste],
            ).pack(side="left", padx=5)
        ttk.Checkbutton(
            filters,
            text=f"최근 {RECENT_MEAL_DAYS}일 안에 먹은 메뉴 제외",
            variable=self.exclude_recent_var,
        ).grid(
            row=taste_row + 1,
            column=0,
            columnspan=4,
            sticky="w",
            padx=5,
            pady=(2, 4),
        )
        actions = ttk.Frame(parent, style="App.TFrame")
        actions.pack(fill="x", pady=(14, 12))
        ttk.Button(
            actions,
            text="조건으로 찾기",
            style="Primary.TButton",
            command=self._find_by_filters,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="랜덤 추천",
            style="Primary.TButton",
            command=self._recommend_random,
        ).pack(side="left", padx=8)
        ttk.Button(
            actions, text="다시 추천", command=self._recommend_random
        ).pack(side="left")
        ttk.Button(
            actions, text="조건 초기화", command=self._clear_filters
        ).pack(side="left")
        self.favorite_action_button = ttk.Button(
            actions, text="☆ 즐겨찾기", command=self._toggle_selected_favorite
        )
        self.favorite_action_button.pack(side="left", padx=(8, 0))
        ttk.Button(
            actions, text="선택 메뉴 기록", command=self._record_selected
        ).pack(side="right")

        result_header = ttk.Frame(parent, style="App.TFrame")
        result_header.pack(fill="x", pady=(0, 7))
        ttk.Label(result_header, text="메뉴 목록", style="Section.TLabel").pack(
            side="left"
        )
        self.result_status = ttk.Label(result_header, text="", style="Muted.TLabel")
        self.result_status.pack(side="right")
        self.menu_tree = self._create_tree(
            parent,
            (
                ("name", "이름", 180),
                ("price", "예상 가격", 120),
                ("description", "음식 설명", 600),
            ),
        )
        self.menu_tree.column("name", anchor="w")
        self.menu_tree.column("description", anchor="w", stretch=True)
        self.menu_tree.bind("<<TreeviewSelect>>", self._show_menu_description)
        self.description_card = ttk.Frame(
            parent, padding=(14, 10), style="Info.TFrame"
        )
        self.description_card.pack(fill="x", pady=(10, 0))
        ttk.Label(
            self.description_card, text="한 줄 맛보기", style="CardTitle.TLabel"
        ).pack(anchor="w", pady=(0, 4))
        self.description_image_label = ttk.Label(self.description_card)
        self.description_image_label.pack(side="left", padx=(0, 12))
        self.description_label = ttk.Label(
            self.description_card,
            text="메뉴를 선택하면 설명이 표시됩니다.",
            style="CardBody.TLabel",
            wraplength=650,
            justify="left",
        )
        self.description_label.pack(side="left", fill="x", expand=True)
        self.description_photo: tk.PhotoImage | None = None

    def _build_history_tab(self, parent: ttk.Frame) -> None:
        controls = ttk.Frame(parent, style="App.TFrame")
        controls.pack(fill="x", pady=(0, 10))
        ttk.Label(controls, text="통계 기간", style="Section.TLabel").pack(side="left")
        self.period_var = tk.StringVar(value="전체")
        period_box = ttk.Combobox(
            controls,
            textvariable=self.period_var,
            values=("전체", "일별 (최근 14일)", "월별 (최근 12개월)"),
            state="readonly",
            width=22,
        )
        period_box.pack(side="left", padx=8)
        self.period_box = period_box
        period_box.bind("<<ComboboxSelected>>", self._on_period_change)
        ttk.Button(
            controls, text="선택 기록 삭제", command=self._delete_selected_history
        ).pack(side="right")

        summary = ttk.Frame(parent, style="App.TFrame")
        summary.pack(fill="x", pady=(0, 14))
        self.meal_count_label = self._create_metric(
            summary, "식사 횟수", "0회", 0
        )
        self.total_spending_label = self._create_metric(
            summary, "총 지출", "0원", 1
        )
        self.average_spending_label = self._create_metric(
            summary, "평균 지출", "0원", 2
        )
        for column in range(3):
            summary.columnconfigure(column, weight=1, uniform="metrics")

        stats_notebook = ttk.Notebook(parent)
        stats_notebook.pack(fill="both", expand=True)
        spending_tab = ttk.Frame(stats_notebook, padding=10)
        preference_tab = ttk.Frame(stats_notebook, padding=10)
        records_tab = ttk.Frame(stats_notebook, padding=10)
        stats_notebook.add(spending_tab, text="지출 그래프")
        stats_notebook.add(preference_tab, text="음식 선호도")
        stats_notebook.add(records_tab, text="식사 기록")

        self.chart_caption = ttk.Label(spending_tab, text="")
        self.chart_caption.pack(anchor="w", pady=(0, 8))
        self.spending_chart = tk.Canvas(
            spending_tab,
            height=300,
            background=self.COLORS["surface"],
            highlightthickness=0,
        )
        self.spending_chart.pack(fill="both", expand=True)
        self.spending_chart.bind("<Configure>", self._on_chart_resize)

        ttk.Label(
            preference_tab,
            text="음식 종류별 선호도와 지출",
            style="Section.TLabel",
        ).pack(
            anchor="w", pady=(0, 8)
        )
        self.category_tree = self._create_tree(
            preference_tab,
            (
                ("category", "음식 종류", 180),
                ("count", "횟수", 100),
                ("preference", "비율", 100),
                ("spending", "지출", 140),
            ),
            height=8,
        )
        ttk.Label(
            preference_tab, text="자주 먹은 메뉴", style="Section.TLabel"
        ).pack(
            anchor="w", pady=(14, 8)
        )
        self.favorite_tree = self._create_tree(
            preference_tab,
            (("name", "메뉴", 180), ("count", "횟수", 100)),
            height=4,
        )
        ttk.Label(records_tab, text="기록을 선택한 뒤 삭제할 수 있습니다.").pack(
            anchor="w", pady=(0, 6)
        )
        self.history_tree = self._create_tree(
            records_tab,
            (
                ("date", "날짜", 140),
                ("name", "메뉴", 200),
                ("category", "음식 종류", 140),
                ("amount", "지출", 140),
                ("memo", "메모", 180),
            ),
        )
        self.history_tree.bind("<<TreeviewSelect>>", self._show_history_detail)
        self.history_detail_label = ttk.Label(
            records_tab,
            text="기록을 선택하면 장소와 메모를 확인할 수 있습니다.",
            style="CardBody.TLabel",
            wraplength=850,
            justify="left",
        )
        self.history_detail_label.pack(fill="x", anchor="w", pady=(8, 0))
        export_actions = ttk.Frame(records_tab, style="App.TFrame")
        export_actions.pack(fill="x", pady=(10, 0))
        ttk.Button(
            export_actions,
            text="기록을 CSV로 내보내기",
            command=self._export_history_csv,
        ).pack(side="left")
        ttk.Button(
            export_actions,
            text="데이터 백업 만들기",
            command=self._backup_data,
        ).pack(side="left", padx=8)

    def _build_favorites_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="다시 먹고 싶은 메뉴를 모아두세요.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 10))
        actions = ttk.Frame(parent, style="App.TFrame")
        actions.pack(fill="x", pady=(0, 8))
        ttk.Button(
            actions, text="즐겨찾기에서 추천", command=self._recommend_favorite
        ).pack(side="left")
        ttk.Button(
            actions, text="즐겨찾기 식사 기록", command=self._record_favorite
        ).pack(side="left", padx=8)
        ttk.Button(
            actions, text="선택 해제", command=self._remove_selected_favorite
        ).pack(side="left")
        self.favorites_count_label = ttk.Label(
            actions, text="즐겨찾기 0개", style="Muted.TLabel"
        )
        self.favorites_count_label.pack(side="right")
        self.favorites_tree = self._create_tree(
            parent,
            (
                ("name", "메뉴", 220),
                ("price", "가격", 120),
                ("category", "종류", 140),
                ("diet", "식단 태그", 160),
            ),
        )
        self.favorites_tree.bind(
            "<Double-1>", self._on_favorite_double_click
        )

    def _build_manage_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="메뉴를 추가하거나 선택한 메뉴를 수정·삭제할 수 있습니다.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 10))
        actions = ttk.Frame(parent, style="App.TFrame")
        actions.pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="메뉴 추가", command=self._add_menu).pack(side="left")
        ttk.Button(actions, text="선택 메뉴 수정", command=self._edit_selected_menu).pack(
            side="left", padx=8
        )
        ttk.Button(actions, text="선택 메뉴 삭제", command=self._delete_selected_menu).pack(
            side="left"
        )
        self.manage_count_label = ttk.Label(
            actions, text=f"등록 메뉴 {len(self.menus)}가지", style="Muted.TLabel"
        )
        self.manage_count_label.pack(side="right", padx=4)
        self.manage_tree = self._create_tree(
            parent,
            (
                ("name", "메뉴", 180),
                ("price", "가격", 110),
                ("category", "종류", 100),
                ("spice", "맵기", 100),
                ("meal_type", "식사 방식", 100),
                ("meal_categories", "메뉴 구분", 140),
                ("staple", "주식", 70),
                ("soup", "국물", 70),
                ("temperature", "온도", 85),
                ("tastes", "맛 특징", 180),
            ),
        )
        self.manage_tree.bind("<<TreeviewSelect>>", self._show_managed_menu_description)
        manage_detail = ttk.Frame(parent, padding=10, style="Info.TFrame")
        manage_detail.pack(fill="x", pady=(8, 0))
        self.manage_image_label = ttk.Label(manage_detail)
        self.manage_image_label.pack(side="left", padx=(0, 12))
        self.manage_description_label = ttk.Label(
            manage_detail,
            text="메뉴를 선택하면 설명이 표시됩니다.",
            wraplength=700,
            justify="left",
        )
        self.manage_description_label.pack(side="left", fill="x", expand=True)
        self.manage_photo: tk.PhotoImage | None = None

    def _create_tree(
        self,
        parent: ttk.Frame,
        columns: tuple[tuple[str, str, int], ...],
        *,
        height: int = 10,
    ) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        names = tuple(column[0] for column in columns)
        tree = ttk.Treeview(
            frame, columns=names, show="headings", height=height, selectmode="browse"
        )
        tree.tag_configure("alternate", background=self.COLORS["surface_alt"])
        tree.tag_configure("regular", background=self.COLORS["surface"])
        for key, heading, width in columns:
            tree.heading(key, text=heading)
            tree.column(key, width=width, minwidth=70, anchor="center")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return tree

    def _create_metric(
        self, parent: ttk.Frame, title: str, initial_value: str, column: int
    ) -> ttk.Label:
        card = ttk.Frame(parent, style="Metric.TFrame", padding=(14, 10))
        card.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=(0, 6) if column == 0 else (6, 6),
        )
        ttk.Label(card, text=title, style="MetricTitle.TLabel").pack(anchor="w")
        value = ttk.Label(card, text=initial_value, style="MetricValue.TLabel")
        value.pack(anchor="w", pady=(3, 0))
        return value

    @staticmethod
    def _optional_positive_integer(value: str, label: str) -> int | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            number = int(cleaned)
        except ValueError as error:
            raise ValueError(f"{label}은(는) 숫자로 입력해 주세요.") from error
        if number <= 0:
            raise ValueError(f"{label}은(는) 1 이상의 정수여야 합니다.")
        return number

    def _find_by_filters(self) -> None:
        matches = self._matching_menus()
        if matches is None:
            return
        if not matches:
            self._show_results([], "조건에 맞는 메뉴가 없습니다. 조건을 바꿔 보세요.")
            return
        self._show_results(matches, f"조건에 맞는 메뉴 {len(matches)}개")

    def _matching_menus(self) -> list[dict[str, Any]] | None:
        try:
            min_price = self._optional_positive_integer(
                self.min_price_var.get(), "최소 가격"
            )
            max_price = self._optional_positive_integer(
                self.max_price_var.get(), "최대 가격"
            )
        except ValueError as error:
            messagebox.showerror("입력 확인", str(error), parent=self.root)
            return None
        if min_price is not None and max_price is not None and min_price > max_price:
            messagebox.showerror(
                "입력 확인",
                "최소 가격은 최대 가격보다 클 수 없습니다.",
                parent=self.root,
            )
            return None

        selected_spice = self.spice_var.get()
        max_spice = next(
            (
                level
                for level, label in SPICE_LABELS.items()
                if label == selected_spice
            ),
            None,
        )
        excluded_names = (
            self._recently_eaten_menu_names()
            if self.exclude_recent_var.get()
            else None
        )
        return filter_menus(
            self.menus,
            category=self._selected_filter(self.category_var.get()),
            max_spice=max_spice,
            meal_type=self._selected_filter(self.meal_type_var.get()),
            meal_category=self._selected_filter(
                self.meal_category_var.get()
            ),
            staple=self._selected_filter(self.staple_var.get()),
            has_soup={
                "국물 있음": True,
                "국물 없음": False,
            }.get(self.soup_var.get()),
            temperature=self._selected_filter(self.temperature_var.get()),
            tastes=[
                taste
                for taste, variable in self.filter_taste_vars.items()
                if variable.get()
            ],
            min_price=min_price,
            max_price=max_price,
            diet_tag=next(
                (
                    tag
                    for tag, label in DIET_LABELS.items()
                    if label == self.diet_var.get()
                ),
                None,
            ),
            excluded_names=excluded_names,
        )

    @staticmethod
    def _selected_filter(value: str) -> str | None:
        return None if value == "상관없음" else value

    def _recently_eaten_menu_names(self) -> set[str]:
        cutoff = date.today() - timedelta(days=RECENT_MEAL_DAYS - 1)
        return {
            entry["name"]
            for entry in self.history
            if cutoff <= date.fromisoformat(entry["date"]) <= date.today()
        }

    def _recommend_random(self) -> None:
        matches = self._matching_menus()
        if matches is None:
            return
        if not matches:
            self._show_results(
                [], "조건에 맞는 메뉴가 없습니다. 필터를 바꾸거나 최근 메뉴 제외를 해제해 보세요."
            )
            return
        menu = random.choice(matches)
        self._show_results([menu], "선택한 조건에 맞는 메뉴를 추천합니다.")
        self.menu_tree.selection_set("0")
        self.menu_tree.focus("0")
        self._show_menu_description()

    def _clear_filters(self) -> None:
        self.min_price_var.set("")
        self.max_price_var.set("")
        self.category_var.set("상관없음")
        self.spice_var.set("상관없음")
        self.meal_type_var.set("상관없음")
        self.meal_category_var.set("상관없음")
        self.staple_var.set("상관없음")
        self.soup_var.set("상관없음")
        self.temperature_var.set("상관없음")
        self.diet_var.set("상관없음")
        self.exclude_recent_var.set(True)
        for variable in self.filter_taste_vars.values():
            variable.set(False)
        self._show_results(self.menus, f"등록된 메뉴 {len(self.menus)}개")

    def _show_results(
        self, menus: list[dict[str, Any]], status: str
    ) -> None:
        self.visible_menus = menus
        for item in self.menu_tree.get_children():
            self.menu_tree.delete(item)
        for index, menu in enumerate(menus):
            self.menu_tree.insert(
                "",
                "end",
                iid=str(index),
                tags=("alternate" if index % 2 else "regular",),
                values=(
                    menu["name"],
                    f"{menu['price']:,}원",
                    menu.get("description") or "설명이 등록되지 않았습니다.",
                ),
            )
        self.result_status.configure(text=status)
        self.description_label.configure(text="메뉴를 선택하면 설명이 표시됩니다.")
        self.description_image_label.configure(image="", text="사진 미등록")
        self.description_photo = None
        self.favorite_action_button.configure(text="☆ 즐겨찾기")

    def _load_thumbnail(self, path: Path) -> tk.PhotoImage | None:
        try:
            image = tk.PhotoImage(master=self.root, file=str(path))
        except (OSError, tk.TclError) as error:
            messagebox.showerror(
                "사진 표시 오류",
                f"사진 파일을 열지 못했습니다.\n{path}\n{error}",
                parent=self.root,
            )
            return None
        scale = max(
            1,
            (image.width() + 239) // 240,
            (image.height() + 159) // 160,
        )
        return image.subsample(scale, scale)

    def _show_menu_image(
        self, label: ttk.Label, menu: dict[str, Any]
    ) -> tk.PhotoImage | None:
        image_path = _resolve_menu_image(menu.get("image", ""))
        if image_path is None:
            label.configure(image="", text="사진 미등록")
            return None
        photo = self._load_thumbnail(image_path)
        label.configure(
            image=photo if photo is not None else "",
            text="" if photo is not None else "사진을 표시할 수 없습니다.",
        )
        return photo

    def _show_menu_description(self, event: tk.Event[Any] | None = None) -> None:
        tree = event.widget if event is not None else self.menu_tree
        selected = tree.selection()
        if selected:
            menu = self.visible_menus[int(selected[0])]
            description = menu.get("description") or "등록된 설명이 없습니다."
            self.description_label.configure(text=description)
            self.description_photo = self._show_menu_image(
                self.description_image_label, menu
            )
            self.favorite_action_button.configure(
                text=(
                    "★ 즐겨찾기 해제"
                    if menu["name"] in self.favorites
                    else "☆ 즐겨찾기 추가"
                )
            )

    def _show_managed_menu_description(
        self, event: tk.Event[Any] | None = None
    ) -> None:
        tree = event.widget if event is not None else self.manage_tree
        selected = tree.selection()
        if selected:
            menu = self.menus[int(selected[0])]
            description = menu.get("description") or "등록된 설명이 없습니다."
            self.manage_description_label.configure(text=description)
            self.manage_photo = self._show_menu_image(
                self.manage_image_label, menu
            )

    def _refresh_menu_lists(self) -> None:
        categories = sorted({menu["category"] for menu in self.menus})
        meal_types = sorted({menu["meal_type"] for menu in self.menus})
        self.category_box.configure(values=["상관없음", *categories])
        self.meal_type_box.configure(values=["상관없음", *meal_types])
        self.restaurant_category_box.configure(values=("전체", *categories))
        self.menu_count_label.configure(text=f"메뉴 {len(self.menus)}가지")
        self.manage_count_label.configure(text=f"등록 메뉴 {len(self.menus)}가지")
        self._clear_filters()
        for item in self.manage_tree.get_children():
            self.manage_tree.delete(item)
        for index, menu in enumerate(self.menus):
            self.manage_tree.insert(
                "",
                "end",
                iid=str(index),
                tags=("alternate" if index % 2 else "regular",),
                values=(
                    menu["name"],
                    f"{menu['price']:,}원",
                    menu["category"],
                    SPICE_LABELS[menu["spice_level"]],
                    menu["meal_type"],
                    ", ".join(menu["meal_categories"]),
                    menu["staple"],
                    "있음" if menu["has_soup"] else "없음",
                    menu["temperature"],
                    ", ".join(TASTE_LABELS[taste] for taste in menu["tastes"])
                    or "선택 안 함",
                ),
            )
        self.manage_description_label.configure(
            text="메뉴를 선택하면 설명이 표시됩니다."
        )
        self.manage_image_label.configure(image="", text="사진 미등록")
        self.manage_photo = None
        self._refresh_favorites()

    def _toggle_selected_favorite(self) -> None:
        selected = self.menu_tree.selection()
        if not selected:
            messagebox.showinfo(
                "메뉴 선택", "즐겨찾기에 추가할 메뉴를 먼저 선택해 주세요.", parent=self.root
            )
            return
        name = self.visible_menus[int(selected[0])]["name"]
        updated = self.favorites.copy()
        if name in updated:
            updated.remove(name)
        else:
            updated.add(name)
        if not save_favorites(
            updated,
            path=FAVORITES_FILE,
            on_error=lambda error: messagebox.showerror(
                "저장 오류", error, parent=self.root
            ),
        ):
            return
        self.favorites = updated
        self._refresh_favorites()
        self._show_menu_description()

    def _refresh_favorites(self) -> None:
        if not hasattr(self, "favorites_tree"):
            return
        self.visible_favorites = [
            menu for menu in self.menus if menu["name"] in self.favorites
        ]
        for item in self.favorites_tree.get_children():
            self.favorites_tree.delete(item)
        for index, menu in enumerate(self.visible_favorites):
            self.favorites_tree.insert(
                "",
                "end",
                iid=str(index),
                tags=("alternate" if index % 2 else "regular",),
                values=(
                    menu["name"],
                    f"{menu['price']:,}원",
                    menu["category"],
                    ", ".join(DIET_LABELS[tag] for tag in menu["diet_tags"])
                    or "미지정",
                ),
            )
        self.favorites_count_label.configure(
            text=f"즐겨찾기 {len(self.visible_favorites)}개"
        )
        self.favorites = {menu["name"] for menu in self.visible_favorites}

    def _selected_favorite(self) -> dict[str, Any] | None:
        selected = self.favorites_tree.selection()
        if not selected:
            messagebox.showinfo(
                "즐겨찾기 선택", "즐겨찾기 메뉴를 먼저 선택해 주세요.", parent=self.root
            )
            return None
        return self.visible_favorites[int(selected[0])]

    def _remove_selected_favorite(self) -> None:
        menu = self._selected_favorite()
        if menu is None:
            return
        updated = self.favorites - {menu["name"]}
        if not save_favorites(
            updated,
            path=FAVORITES_FILE,
            on_error=lambda error: messagebox.showerror(
                "저장 오류", error, parent=self.root
            ),
        ):
            return
        self.favorites = updated
        self._refresh_favorites()

    def _recommend_favorite(self) -> None:
        matches = self._matching_menus()
        if matches is None:
            return
        candidates = [menu for menu in matches if menu["name"] in self.favorites]
        if not candidates:
            messagebox.showinfo(
                "즐겨찾기 추천",
                "현재 추천 조건에 맞는 즐겨찾기 메뉴가 없습니다.",
                parent=self.root,
            )
            return
        selected = random.choice(candidates)
        self.main_notebook.select(self.recommend_tab)
        self._show_results([selected], "즐겨찾기 메뉴 중에서 추천합니다.")
        self.menu_tree.selection_set("0")
        self.menu_tree.focus("0")
        self._show_menu_description()

    def _record_favorite(self) -> None:
        menu = self._selected_favorite()
        if menu is not None:
            self._record_menu(menu)

    def _on_favorite_double_click(self, event: tk.Event[Any]) -> None:
        if event.widget is self.favorites_tree:
            self._record_favorite()

    def _export_history_csv(self) -> None:
        if not self.history:
            messagebox.showinfo(
                "내보내기", "내보낼 식사 기록이 없습니다.", parent=self.root
            )
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="식사 기록 CSV 저장",
            defaultextension=".csv",
            filetypes=(("CSV 파일", "*.csv"), ("모든 파일", "*.*")),
            initialfile="meal_history.csv",
        )
        if not path:
            return
        destination = Path(path).resolve()
        protected_files = {
            MENU_FILE.resolve(),
            HISTORY_FILE.resolve(),
            FAVORITES_FILE.resolve(),
            PREFERENCES_FILE.resolve(),
        }
        if destination in protected_files:
            messagebox.showerror(
                "저장 위치 확인",
                "원본 메뉴·기록·즐겨찾기·설정 파일에는 내보낼 수 없습니다.",
                parent=self.root,
            )
            return
        try:
            with Path(path).open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=(
                        "date",
                        "name",
                        "category",
                        "amount",
                        "location",
                        "companions",
                        "want_again",
                        "note",
                    ),
                )
                writer.writeheader()
                writer.writerows(
                    {
                        "date": entry["date"],
                        "name": entry["name"],
                        "category": entry["category"],
                        "amount": entry["amount"],
                        "location": entry.get("location", ""),
                        "companions": entry.get("companions", ""),
                        "want_again": entry.get("want_again", False),
                        "note": entry.get("note", ""),
                    }
                    for entry in self.history
                )
        except OSError as error:
            messagebox.showerror(
                "내보내기 오류",
                f"CSV 파일을 저장하지 못했습니다: {error}",
                parent=self.root,
            )
            return
        messagebox.showinfo(
            "내보내기 완료",
            f"식사 기록 {len(self.history)}건을 저장했습니다.",
            parent=self.root,
        )

    def _backup_data(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="데이터 백업 저장",
            defaultextension=".zip",
            filetypes=(("ZIP 백업 파일", "*.zip"),),
            initialfile=f"menu_backup_{date.today().isoformat()}.zip",
        )
        if not path:
            return
        destination = Path(path).resolve()
        protected_files = {
            MENU_FILE.resolve(),
            HISTORY_FILE.resolve(),
            FAVORITES_FILE.resolve(),
            PREFERENCES_FILE.resolve(),
        }
        if destination in protected_files:
            messagebox.showerror(
                "저장 위치 확인",
                "원본 메뉴·기록·즐겨찾기·설정 파일에는 백업을 저장할 수 없습니다.",
                parent=self.root,
            )
            return
        image_paths: set[Path] = set()
        for menu in self.menus:
            image_value = menu.get("image", "")
            if not image_value:
                continue
            image_path = _resolve_menu_image(image_value)
            if image_path is None:
                messagebox.showerror(
                    "백업 오류",
                    f"'{menu['name']}' 메뉴의 사진 파일을 찾을 수 없어 백업할 수 없습니다.",
                    parent=self.root,
                )
                return
            image_paths.add(image_path)
        try:
            with zipfile.ZipFile(
                path, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.write(MENU_FILE, arcname=MENU_FILE.name)
                archive.writestr(
                    HISTORY_FILE.name,
                    json.dumps(self.history, ensure_ascii=False, indent=2) + "\n",
                )
                archive.writestr(
                    FAVORITES_FILE.name,
                    json.dumps(sorted(self.favorites), ensure_ascii=False, indent=2)
                    + "\n",
                )
                for image_path in sorted(image_paths):
                    archive.write(
                        image_path,
                        arcname=image_path.relative_to(BASE_DIR).as_posix(),
                    )
        except OSError as error:
            messagebox.showerror(
                "백업 오류",
                f"백업 파일을 만들지 못했습니다: {error}",
                parent=self.root,
            )
            return
        messagebox.showinfo(
            "백업 완료",
            "메뉴·사진·식사 기록·즐겨찾기를 ZIP으로 저장했습니다.",
            parent=self.root,
        )

    def _add_menu(self) -> None:
        self._open_menu_editor()

    def _edit_selected_menu(self) -> None:
        selected = self.manage_tree.selection()
        if not selected:
            messagebox.showinfo(
                "메뉴 선택", "수정할 메뉴를 먼저 선택해 주세요.", parent=self.root
            )
            return
        self._open_menu_editor(int(selected[0]))

    def _open_menu_editor(self, index: int | None = None) -> None:
        existing = self.menus[index] if index is not None else {}
        dialog = tk.Toplevel(self.root)
        dialog.title("메뉴 수정" if index is not None else "메뉴 추가")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)

        name_var = tk.StringVar(value=existing.get("name", ""))
        price_var = tk.StringVar(value=str(existing.get("price", "")))
        category_var = tk.StringVar(value=existing.get("category", ""))
        spice_var = tk.StringVar(
            value=SPICE_LABELS.get(existing.get("spice_level"), "안 매움")
        )
        meal_type_var = tk.StringVar(value=existing.get("meal_type", ""))
        staple_var = tk.StringVar(value=existing.get("staple", STAPLE_CHOICES[0]))
        soup_var = tk.StringVar(
            value="있음" if existing.get("has_soup", False) else "없음"
        )
        temperature_var = tk.StringVar(
            value=existing.get("temperature", TEMPERATURE_CHOICES[0])
        )
        taste_vars = {
            taste: tk.BooleanVar(value=taste in existing.get("tastes", []))
            for taste in TASTE_LABELS
        }
        diet_vars = {
            tag: tk.BooleanVar(value=tag in existing.get("diet_tags", []))
            for tag in DIET_LABELS
        }
        meal_category_vars = {
            category_name: tk.BooleanVar(
                value=category_name
                in existing.get("meal_categories", ["식사"])
            )
            for category_name in MEAL_CATEGORIES
        }
        inputs: list[tuple[str, tk.StringVar, tuple[str, ...] | None]] = [
            ("메뉴 이름", name_var, None),
            ("가격 (원)", price_var, None),
            ("음식 종류", category_var, None),
            ("맵기", spice_var, tuple(SPICE_LABELS.values())),
            ("식사 방식", meal_type_var, None),
            ("주식", staple_var, STAPLE_CHOICES),
            ("국물", soup_var, ("있음", "없음")),
            ("온도", temperature_var, TEMPERATURE_CHOICES),
        ]
        for row, (label, variable, choices) in enumerate(inputs):
            ttk.Label(frame, text=label).grid(
                row=row, column=0, sticky="w", padx=(0, 10), pady=5
            )
            if choices:
                field: tk.Widget = ttk.Combobox(
                    frame, textvariable=variable, values=choices, state="readonly"
                )
            else:
                field = ttk.Entry(frame, textvariable=variable, width=32)
            field.grid(row=row, column=1, sticky="ew", pady=5)

        tastes_row = len(inputs)
        ttk.Label(frame, text="맛 특징 (복수 선택)").grid(
            row=tastes_row, column=0, sticky="nw", padx=(0, 10), pady=5
        )
        taste_frame = ttk.Frame(frame)
        taste_frame.grid(row=tastes_row, column=1, sticky="w", pady=5)
        for taste, label in TASTE_LABELS.items():
            ttk.Checkbutton(
                taste_frame, text=label, variable=taste_vars[taste]
            ).pack(side="left", padx=(0, 8))

        diet_row = tastes_row + 1
        ttk.Label(frame, text="식단 태그 (선호 정보)").grid(
            row=diet_row, column=0, sticky="nw", padx=(0, 10), pady=5
        )
        diet_frame = ttk.Frame(frame)
        diet_frame.grid(row=diet_row, column=1, sticky="w", pady=5)
        for tag, label in DIET_LABELS.items():
            ttk.Checkbutton(
                diet_frame, text=label, variable=diet_vars[tag]
            ).pack(side="left", padx=(0, 8))

        meal_category_row = diet_row + 1
        ttk.Label(frame, text="메뉴 구분 (복수 선택)").grid(
            row=meal_category_row,
            column=0,
            sticky="nw",
            padx=(0, 10),
            pady=5,
        )
        meal_category_frame = ttk.Frame(frame)
        meal_category_frame.grid(
            row=meal_category_row, column=1, sticky="w", pady=5
        )
        for category_name in MEAL_CATEGORIES:
            ttk.Checkbutton(
                meal_category_frame,
                text=category_name,
                variable=meal_category_vars[category_name],
            ).pack(side="left", padx=(0, 8))

        description_row = meal_category_row + 1
        ttk.Label(frame, text="메뉴 설명").grid(
            row=description_row, column=0, sticky="nw", padx=(0, 10), pady=5
        )
        description = tk.Text(frame, width=34, height=4, wrap="word")
        description.grid(row=description_row, column=1, sticky="ew", pady=5)
        description.insert("1.0", existing.get("description", ""))

        selected_image_source: Path | None = None
        remove_image = False
        editor_photo: tk.PhotoImage | None = None
        existing_image = existing.get("image", "")
        existing_image_path = _resolve_menu_image(existing_image)
        image_status_var = tk.StringVar(
            value=existing_image_path.name if existing_image_path else "사진 미등록"
        )
        image_row = description_row + 1
        ttk.Label(frame, text="메뉴 사진 (PNG/GIF)").grid(
            row=image_row, column=0, sticky="nw", padx=(0, 10), pady=5
        )
        image_controls = ttk.Frame(frame)
        image_controls.grid(row=image_row, column=1, sticky="w", pady=5)
        image_preview_label = ttk.Label(image_controls, text="사진 미등록")
        image_preview_label.pack(side="left", padx=(0, 10))
        ttk.Label(image_controls, textvariable=image_status_var).pack(
            side="left", padx=(0, 10)
        )

        def choose_image() -> None:
            nonlocal selected_image_source, remove_image, editor_photo
            selected = filedialog.askopenfilename(
                parent=dialog,
                title="메뉴 사진 선택",
                filetypes=(
                    ("지원 이미지", "*.png *.gif"),
                    ("PNG 이미지", "*.png"),
                    ("GIF 이미지", "*.gif"),
                ),
            )
            if not selected:
                return
            source = Path(selected)
            if source.suffix.casefold() not in MENU_IMAGE_EXTENSIONS:
                messagebox.showerror(
                    "사진 형식 확인",
                    "PNG 또는 GIF 사진만 사용할 수 있습니다.",
                    parent=dialog,
                )
                return
            preview = self._load_thumbnail(source)
            if preview is None:
                return
            selected_image_source = source
            remove_image = False
            editor_photo = preview
            image_preview_label.configure(image=preview, text="")
            image_status_var.set(source.name)

        def clear_image() -> None:
            nonlocal selected_image_source, remove_image, editor_photo
            selected_image_source = None
            remove_image = True
            editor_photo = None
            image_preview_label.configure(image="", text="사진 미등록")
            image_status_var.set("사진 없음")

        ttk.Button(
            image_controls, text="사진 선택", command=choose_image
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            image_controls, text="사진 제거", command=clear_image
        ).pack(side="left")
        if existing_image_path is not None:
            editor_photo = self._load_thumbnail(existing_image_path)
            if editor_photo is not None:
                image_preview_label.configure(image=editor_photo, text="")

        frame.columnconfigure(1, weight=1)

        def submit() -> None:
            name = name_var.get().strip()
            category = category_var.get().strip()
            meal_type = meal_type_var.get().strip()
            if not name or not category or not meal_type:
                messagebox.showerror(
                    "입력 확인",
                    "메뉴 이름, 음식 종류, 식사 방식을 모두 입력해 주세요.",
                    parent=dialog,
                )
                return
            try:
                price = self._optional_positive_integer(price_var.get(), "가격")
            except ValueError as error:
                messagebox.showerror("입력 확인", str(error), parent=dialog)
                return
            if price is None:
                messagebox.showerror(
                    "입력 확인", "가격을 입력해 주세요.", parent=dialog
                )
                return
            duplicates = [
                menu
                for current_index, menu in enumerate(self.menus)
                if current_index != index and menu["name"].casefold() == name.casefold()
            ]
            if duplicates:
                messagebox.showerror(
                    "입력 확인", "같은 이름의 메뉴가 이미 있습니다.", parent=dialog
                )
                return
            selected_meal_categories = [
                category_name
                for category_name, variable in meal_category_vars.items()
                if variable.get()
            ]
            if not selected_meal_categories:
                messagebox.showerror(
                    "입력 확인",
                    "메뉴 구분을 하나 이상 선택해 주세요.",
                    parent=dialog,
                )
                return
            image_value = "" if remove_image else existing_image
            new_image_path: Path | None = None
            if selected_image_source is not None:
                temporary_image_path: Path | None = None
                try:
                    MENU_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
                    new_image_path = MENU_IMAGE_DIR / (
                        f"{uuid4().hex}{selected_image_source.suffix.lower()}"
                    )
                    temporary_image_path = new_image_path.with_name(
                        f"{new_image_path.name}.tmp"
                    )
                    shutil.copyfile(
                        selected_image_source, temporary_image_path
                    )
                    temporary_image_path.replace(new_image_path)
                except OSError as error:
                    if temporary_image_path is not None:
                        try:
                            temporary_image_path.unlink(missing_ok=True)
                        except OSError as cleanup_error:
                            error = OSError(
                                f"{error}; 임시 사진 파일도 삭제하지 못했습니다: "
                                f"{cleanup_error}"
                            )
                    messagebox.showerror(
                        "사진 저장 오류",
                        f"메뉴 사진을 저장하지 못했습니다: {error}",
                        parent=dialog,
                    )
                    return
                image_value = new_image_path.relative_to(BASE_DIR).as_posix()
            menu = {
                "name": name,
                "price": price,
                "category": category,
                "spice_level": next(
                    level
                    for level, label in SPICE_LABELS.items()
                    if label == spice_var.get()
                ),
                "meal_type": meal_type,
                "staple": staple_var.get(),
                "has_soup": soup_var.get() == "있음",
                "temperature": temperature_var.get(),
                "tastes": [
                    taste for taste, variable in taste_vars.items() if variable.get()
                ],
                "diet_tags": [
                    tag for tag, variable in diet_vars.items() if variable.get()
                ],
                "meal_categories": selected_meal_categories,
                "image": image_value,
                "description": description.get("1.0", "end-1c").strip(),
            }
            updated_menus = self.menus.copy()
            if index is None:
                updated_menus.append(menu)
            else:
                updated_menus[index] = menu
            if not save_menus(
                updated_menus,
                on_error=lambda error: messagebox.showerror(
                    "저장 오류", error, parent=dialog
                ),
            ):
                if new_image_path is not None:
                    try:
                        new_image_path.unlink(missing_ok=True)
                    except OSError as error:
                        messagebox.showerror(
                            "사진 정리 오류",
                            f"저장하지 못한 사진 파일을 삭제할 수 없습니다: {error}",
                            parent=dialog,
                        )
                return
            previous_image = existing.get("image", "")
            previous_name = existing.get("name")
            self.menus[:] = updated_menus
            if previous_image and previous_image != image_value:
                self._remove_unused_menu_image(previous_image, self.menus)
            if previous_name in self.favorites and previous_name != name:
                favorites = self.favorites - {previous_name} | {name}
                if save_favorites(
                    favorites,
                    path=FAVORITES_FILE,
                    on_error=lambda error: messagebox.showerror(
                        "저장 오류", error, parent=self.root
                    ),
                ):
                    self.favorites = favorites
            self._refresh_menu_lists()
            self._refresh_history()
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(
            row=image_row + 1,
            column=0,
            columnspan=2,
            sticky="e",
            pady=(10, 0),
        )
        ttk.Button(buttons, text="취소", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="저장", command=submit).pack(
            side="right", padx=(0, 8)
        )
        dialog.bind("<Return>", lambda event: submit() if event.widget is dialog else None)
        dialog.grab_set()
        dialog.focus_set()

    def _delete_selected_menu(self) -> None:
        selected = self.manage_tree.selection()
        if not selected:
            messagebox.showinfo(
                "메뉴 선택", "삭제할 메뉴를 먼저 선택해 주세요.", parent=self.root
            )
            return
        index = int(selected[0])
        name = self.menus[index]["name"]
        if not messagebox.askyesno(
            "메뉴 삭제", f"'{name}' 메뉴를 삭제할까요?", parent=self.root
        ):
            return
        updated_menus = self.menus.copy()
        updated_menus.pop(index)
        if not save_menus(
            updated_menus,
            on_error=lambda error: messagebox.showerror(
                "저장 오류", error, parent=self.root
            ),
        ):
            return
        removed_image = self.menus[index].get("image", "")
        self.menus[:] = updated_menus
        if removed_image:
            self._remove_unused_menu_image(removed_image, self.menus)
        if name in self.favorites:
            favorites = self.favorites - {name}
            if save_favorites(
                favorites,
                path=FAVORITES_FILE,
                on_error=lambda error: messagebox.showerror(
                    "저장 오류", error, parent=self.root
                ),
            ):
                self.favorites = favorites
        self._refresh_menu_lists()
        self._refresh_history()

    def _remove_unused_menu_image(
        self, image: str, menus: list[dict[str, Any]]
    ) -> None:
        if any(menu.get("image") == image for menu in menus):
            return
        image_path = _resolve_menu_image(image)
        if image_path is None:
            return
        try:
            image_path.unlink(missing_ok=True)
        except OSError as error:
            messagebox.showwarning(
                "사진 정리 오류",
                f"메뉴에서 분리된 사진 파일을 삭제하지 못했습니다: {error}",
                parent=self.root,
            )

    def _record_selected(self) -> None:
        selected = self.menu_tree.selection()
        if not selected:
            messagebox.showinfo(
                "메뉴 선택", "기록할 메뉴를 목록에서 먼저 선택해 주세요.", parent=self.root
            )
            return
        self._record_menu(self.visible_menus[int(selected[0])])

    def _record_menu(self, menu: dict[str, Any]) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("식사 기록")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame, text=f"{menu['name']} 식사 기록", style="Section.TLabel"
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        amount_var = tk.StringVar(value=str(menu["price"]))
        location_var = tk.StringVar()
        companions_var = tk.StringVar()
        want_again_var = tk.BooleanVar(value=False)
        ttk.Label(frame, text="실제 지출액 (원)").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=5
        )
        amount_entry = ttk.Entry(frame, textvariable=amount_var, width=36)
        amount_entry.grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Label(frame, text="먹은 장소").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=5
        )
        ttk.Entry(frame, textvariable=location_var, width=36).grid(
            row=2, column=1, sticky="ew", pady=5
        )
        ttk.Label(frame, text="함께한 사람").grid(
            row=3, column=0, sticky="w", padx=(0, 10), pady=5
        )
        ttk.Entry(frame, textvariable=companions_var, width=36).grid(
            row=3, column=1, sticky="ew", pady=5
        )
        ttk.Checkbutton(
            frame, text="다시 먹고 싶은 메뉴", variable=want_again_var
        ).grid(row=4, column=1, sticky="w", pady=5)
        ttk.Label(frame, text="메모").grid(
            row=5, column=0, sticky="nw", padx=(0, 10), pady=5
        )
        note_text = tk.Text(frame, width=36, height=5, wrap="word")
        note_text.grid(row=5, column=1, sticky="ew", pady=5)
        frame.columnconfigure(1, weight=1)

        result: dict[str, Any] | None = None

        def submit() -> None:
            nonlocal result
            try:
                amount = self._optional_positive_integer(
                    amount_var.get(), "실제 지출액"
                )
            except ValueError as error:
                messagebox.showerror("입력 확인", str(error), parent=dialog)
                return
            if amount is None:
                messagebox.showerror(
                    "입력 확인",
                    "실제 지출액을 입력해 주세요.",
                    parent=dialog,
                )
                return
            result = {
                "date": date.today().isoformat(),
                "name": menu["name"],
                "category": menu["category"],
                "amount": amount,
                "location": location_var.get().strip(),
                "companions": companions_var.get().strip(),
                "want_again": want_again_var.get(),
                "note": note_text.get("1.0", "end-1c").strip(),
            }
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="취소", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="기록 저장", command=submit).pack(
            side="right", padx=(0, 8)
        )
        dialog.bind(
            "<Escape>",
            lambda event: dialog.destroy() if event.widget is dialog else None,
        )
        dialog.grab_set()
        amount_entry.focus_set()
        self.root.wait_window(dialog)
        if result is None:
            return
        self.history.append(result)
        if not save_history(
            self.history,
            on_error=lambda error: messagebox.showerror(
                "저장 오류", error, parent=self.root
            ),
        ):
            self.history.pop()
            return
        self._refresh_history()
        messagebox.showinfo(
            "기록 완료",
            f"{menu['name']} 식사 기록과 메모를 저장했습니다.",
            parent=self.root,
        )

    def _history_for_period(self) -> list[tuple[int, dict[str, Any]]]:
        today = date.today()
        period = self.period_var.get()
        if period == "일별 (최근 14일)":
            start = today - timedelta(days=13)
        elif period == "월별 (최근 12개월)":
            month_index = today.year * 12 + today.month - 1 - 11
            year, month_offset = divmod(month_index, 12)
            start = date(year, month_offset + 1, 1)
        else:
            start = None
        filtered: list[tuple[int, dict[str, Any]]] = []
        for index, entry in enumerate(self.history):
            recorded_on = date.fromisoformat(entry["date"])
            if start is None or start <= recorded_on <= today:
                filtered.append((index, entry))
        return filtered

    def _on_period_change(self, event: tk.Event[Any]) -> None:
        if event.widget is self.period_box:
            self._refresh_history()

    def _refresh_history(self) -> None:
        filtered_history = self._history_for_period()
        self.visible_history = filtered_history
        entries = [entry for _, entry in filtered_history]
        total = sum(entry["amount"] for entry in entries)
        meal_count = len(entries)
        self.meal_count_label.configure(text=f"{meal_count}회")
        self.total_spending_label.configure(text=f"{total:,}원")
        average = total // meal_count if meal_count else 0
        self.average_spending_label.configure(text=f"{average:,}원")

        counts: Counter[str] = Counter()
        spending: defaultdict[str, int] = defaultdict(int)
        for entry in entries:
            counts[entry["category"]] += 1
            spending[entry["category"]] += entry["amount"]
        for tree in (self.category_tree, self.favorite_tree, self.history_tree):
            for item in tree.get_children():
                tree.delete(item)
        for row, (category, count) in enumerate(counts.most_common()):
            self.category_tree.insert(
                "",
                "end",
                tags=("alternate" if row % 2 else "regular",),
                values=(
                    category,
                    f"{count}회",
                    f"{count / meal_count * 100:.1f}%",
                    f"{spending[category]:,}원",
                ),
            )
        menu_counts = Counter(entry["name"] for entry in entries)
        for row, (name, count) in enumerate(menu_counts.most_common(5)):
            self.favorite_tree.insert(
                "",
                "end",
                tags=("alternate" if row % 2 else "regular",),
                values=(name, f"{count}회"),
            )
        for row, (index, entry) in enumerate(reversed(filtered_history)):
            memo_parts = [
                entry.get("location", ""),
                entry.get("companions", ""),
                "다시 먹고 싶음" if entry.get("want_again", False) else "",
                entry.get("note", ""),
            ]
            memo_preview = " · ".join(part for part in memo_parts if part)[:28]
            self.history_tree.insert(
                "",
                "end",
                iid=str(index),
                tags=("alternate" if row % 2 else "regular",),
                values=(
                    entry["date"],
                    entry["name"],
                    entry["category"],
                    f"{entry['amount']:,}원",
                    memo_preview,
                ),
            )
        self.history_detail_label.configure(
            text="기록을 선택하면 장소와 메모를 확인할 수 있습니다."
        )
        self._draw_spending_chart()

    def _show_history_detail(self, event: tk.Event[Any] | None = None) -> None:
        tree = event.widget if event is not None else self.history_tree
        selected = tree.selection()
        if not selected:
            return
        entry = self.history[int(selected[0])]
        details = [
            f"장소: {entry.get('location') or '미입력'}",
            f"함께한 사람: {entry.get('companions') or '미입력'}",
            f"다시 먹고 싶어요: {'예' if entry.get('want_again', False) else '아니요'}",
            f"메모: {entry.get('note') or '없음'}",
        ]
        self.history_detail_label.configure(text="\n".join(details))

    def _spending_series(self) -> list[tuple[str, int]]:
        grouped: defaultdict[date, int] = defaultdict(int)
        daily = self.period_var.get() == "일별 (최근 14일)"
        for _, entry in self._history_for_period():
            recorded_on = date.fromisoformat(entry["date"])
            key = recorded_on if daily else recorded_on.replace(day=1)
            grouped[key] += entry["amount"]
        return [
            (key.strftime("%m-%d" if daily else "%Y-%m"), amount)
            for key, amount in sorted(grouped.items())
        ]

    def _on_chart_resize(self, event: tk.Event[Any]) -> None:
        if event.widget is self.spending_chart:
            self._draw_spending_chart(event.width, event.height)

    def _draw_spending_chart(
        self, requested_width: int | None = None, requested_height: int | None = None
    ) -> None:
        if not hasattr(self, "spending_chart"):
            return
        canvas = self.spending_chart
        canvas.delete("all")
        width = max(requested_width or canvas.winfo_width(), 320)
        height = max(requested_height or canvas.winfo_height(), 220)
        left, right, top, bottom = 58, 18, 22, 42
        chart_width = width - left - right
        chart_height = height - top - bottom
        data = self._spending_series()
        if not data:
            canvas.create_text(
                width / 2,
                height / 2,
                text="선택한 기간에 식사 기록이 없습니다.",
                fill="#64748b",
                font=("맑은 고딕", 11),
            )
            self.chart_caption.configure(text="기간별 지출")
            return

        maximum = max(amount for _, amount in data)
        tick = max(1, maximum // 4)
        axis_max = ((maximum + tick - 1) // tick) * tick
        for step in range(5):
            amount = axis_max * step / 4
            y = top + chart_height * (1 - step / 4)
            canvas.create_line(
                left, y, width - right, y, fill=self.COLORS["border"]
            )
            canvas.create_text(
                left - 8,
                y,
                text=f"{int(amount):,}",
                anchor="e",
                fill=self.COLORS["muted"],
                font=("맑은 고딕", 8),
            )
        slot_width = chart_width / len(data)
        bar_width = max(4, min(36, slot_width * 0.62))
        label_step = max(1, (len(data) + 11) // 12)
        for index, (label, amount) in enumerate(data):
            center_x = left + slot_width * (index + 0.5)
            bar_top = top + chart_height * (1 - amount / axis_max)
            canvas.create_rectangle(
                center_x - bar_width / 2,
                bar_top,
                center_x + bar_width / 2,
                top + chart_height,
                fill=self.COLORS["primary"],
                outline="",
            )
            canvas.create_text(
                center_x,
                max(top + 7, bar_top - 9),
                text=f"{amount:,}",
                fill=self.COLORS["text"],
                font=("맑은 고딕", 8),
            )
            if index % label_step == 0 or index == len(data) - 1:
                canvas.create_text(
                    center_x,
                    top + chart_height + 16,
                    text=label,
                    fill=self.COLORS["muted"],
                    font=("맑은 고딕", 8),
                )
        self.chart_caption.configure(
            text=(
                "최근 14일 일별 지출"
                if self.period_var.get() == "일별 (최근 14일)"
                else "최근 12개월 월별 지출"
                if self.period_var.get() == "월별 (최근 12개월)"
                else "전체 기록 월별 지출"
            )
        )

    def _delete_selected_history(self) -> None:
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showinfo(
                "기록 선택", "삭제할 식사 기록을 먼저 선택해 주세요.", parent=self.root
            )
            return
        index = int(selected[0])
        entry = self.history[index]
        if not messagebox.askyesno(
            "기록 삭제",
            f"{entry['date']} {entry['name']} 기록을 삭제할까요?",
            parent=self.root,
        ):
            return
        removed = self.history.pop(index)
        if not save_history(
            self.history,
            on_error=lambda error: messagebox.showerror(
                "저장 오류", error, parent=self.root
            ),
        ):
            self.history.insert(index, removed)
            return
        self._refresh_history()


def main() -> None:
    root = tk.Tk()
    warnings: list[str] = []
    menus = load_menus(on_warning=warnings.append)
    history = load_history(on_warning=warnings.append)
    favorites = load_favorites(menus, on_warning=warnings.append)
    MenuApp(root, menus, history, favorites)
    if warnings:
        root.after(
            100,
            lambda: messagebox.showwarning(
                "데이터 확인",
                "\n".join(warnings),
                parent=root,
            ),
        )
    root.mainloop()


if __name__ == "__main__":
    main()