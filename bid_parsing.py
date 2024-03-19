import time
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.webdriver import WebDriver
from tqdm import tqdm


def collection_of_totals(
        driver: WebDriver,
        team_name: str,
        personal_total: dict,
        overall_total: dict) -> None:
    opponent_team, desired_team = sorted(
        driver.find_elements(By.CLASS_NAME, 'smh__participantName'),
        key=lambda team: team.text.strip() == team_name
    )

    opponent_totals = (
        int(total.text)
        for total in opponent_team.find_elements(By.XPATH, './following-sibling::div[position()<6]')
    )
    desired_totals = (
        int(total.text)
        for total in desired_team.find_elements(By.XPATH, './following-sibling::div[position()<6]')
    )

    for indx, totals in enumerate(zip(desired_totals, opponent_totals)):
        desired, opponent = totals
        if not indx:
            # Дополнительная проверка, т.к. матч может закончиться не в основное время
            check = driver.find_element(By.CLASS_NAME, 'fixedHeaderDuel__detailStatus')

            if check.text.strip() == 'ЗАВЕРШЕН':
                personal_total['Матч'].append(desired)
                overall_total['Матч'].append(desired + opponent)
            else:
                before_overtime = driver.find_element(
                    By.CSS_SELECTOR, '.detailScore__fullTime span:first-child'
                ).text
                personal_total['Матч'].append(int(before_overtime))
                overall_total['Матч'].append(int(before_overtime) * 2)
        else:
            personal_total[f'{indx} четверть'].append(desired)
            overall_total[f'{indx} четверть'].append(desired + opponent)


def create_stat(total_win, total_lose) -> dict:
    """Шаблон статистики, который содержит каждый матч"""
    return {
        'Количество побед': total_win,
        'Количество поражений': total_lose,
        'Тотал': {
            'Личный': {
                'Матч': [],
                '1 четверть': [],
                '2 четверть': [],
                '3 четверть': [],
                '4 четверть': []
            },
            'Общий': {
                'Матч': [],
                '1 четверть': [],
                '2 четверть': [],
                '3 четверть': [],
                '4 четверть': []
            }
        }
    }


def collect_statistics(driver: WebDriver, team_name: str) -> dict:
    tab = driver.find_element(By.XPATH, f'//div[contains(text(), "{team_name}")]/..')
    win_lose = [w_l.text.strip() for w_l in tab.find_elements(By.CSS_SELECTOR, '.h2h__icon span')]

    stat = create_stat(win_lose.count('В'), win_lose.count('П'))

    for past_match in tab.find_elements(By.CLASS_NAME, 'h2h__row'):
        driver.execute_script('arguments[0].click()', past_match)
        driver.switch_to.window(driver.window_handles[1])

        collection_of_totals(
            driver, team_name,
            personal_total=stat['Тотал']['Личный'],
            overall_total=stat['Тотал']['Общий']
        )

        driver.close()
        browser.switch_to.window(browser.window_handles[0])

    return stat


def get_info_from_card(driver: WebDriver) -> dict:
    """Сбор первичной информации"""
    information = {}
    first, second = (
        team.text
        for team in driver.find_elements(By.CSS_SELECTOR, 'a.participant__participantName')
    )
    name_of_match = f'{first}-VS-{second}'
    information[name_of_match] = {
        first: {'Итого': {}, f'{first} - Дома': {}},
        second: {'Итого': {}, f'{second} - В гостях': {}}
    }

    first_itogo = information[name_of_match][first]['Итого']
    first_home = information[name_of_match][first][f'{first} - Дома']
    second_itogo = information[name_of_match][second]['Итого']
    second_on_visit = information[name_of_match][second][f'{second} - В гостях']

    categories = driver.find_elements(By.CSS_SELECTOR, '._tabsSecondary_33oei_48 ._tab_33oei_5')

    for category in categories:
        driver.execute_script('arguments[0].click()', category)
        title = category.find_element(By.XPATH, '..').get_attribute('title')

        # нажатие на кнопки "показать больше матчей"
        for more in browser.find_elements(By.CLASS_NAME, 'showMore'):
            browser.execute_script("arguments[0].click();", more)

        if title.lower() == 'итого':
            first_itogo.update(collect_statistics(driver, first))
            second_itogo.update(collect_statistics(driver, second))
        elif 'дома' in title.lower():
            first_home.update(collect_statistics(driver, first))
        elif 'в гостях' in title.lower():
            second_on_visit.update(collect_statistics(driver, second))

    return information


def declination_of_matches(amount: int) -> str:
    """Функция возвращает сообщение о количестве матчей в определенном падеже"""
    declensions = ['матч', 'матча', 'матчей']
    if amount % 10 == 1 and amount % 100 != 11:
        return f'{amount} {declensions[0]}'
    elif amount % 10 in (2, 3, 4) and amount % 100 not in (12, 13, 14):
        return f'{amount} {declensions[1]}'
    else:
        return f'{amount} {declensions[2]}'


chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--headless')

link_to_the_matches = 'https://www.livesport.com/ru/basketball/usa/nba/fixtures/'
today = datetime.today()
total_matches = []
match_statistics = []

with webdriver.Chrome(options=chrome_options) as browser:
    browser.implicitly_wait(10)
    browser.get(url=link_to_the_matches)

    # отклонение кук
    browser.find_element(By.CSS_SELECTOR, '#onetrust-reject-all-handler').click()

    # сбор сегодняшних матчей в список
    for match in browser.find_elements(By.CSS_SELECTOR, '.sportName .event__match'):
        event_time = match.find_element(By.CLASS_NAME, 'event__time').text.split()[0]

        if datetime.strptime(f'{event_time}{today.year}', '%d.%m.%Y') > today:
            break

        browser.execute_script("arguments[0].click()", match)
        browser.switch_to.window(browser.window_handles[1])  # переход на карточку матча
        total_matches.append(browser.current_url)
        browser.close()
        browser.switch_to.window(browser.window_handles[0])  # возвращение на основную страницу браузера

if len(total_matches) > 0:
    print(f'На сегодня есть {declination_of_matches(len(total_matches))}')
    time.sleep(1)
    print(f'Начинаю собирать данные с матчей')

    for url_match in tqdm(total_matches):
        with webdriver.Chrome(options=chrome_options) as browser:
            browser.implicitly_wait(10)
            browser.get(url=url_match)

            # отклонение кук
            browser.find_element(By.CSS_SELECTOR, '#onetrust-reject-all-handler').click()

            h2h = browser.find_element(By.XPATH, '//button[text()="H2H"]')
            browser.execute_script('arguments[0].click()', h2h)
            match_statistics.append(get_info_from_card(driver=browser))

    with open(
            f'match_information/matches_on_{today.strftime("%d.%m.%Y")}.json',
            'w', encoding='utf-8') as file:
        json.dump(match_statistics, file, indent=4, ensure_ascii=False)
else:
    print('На сегодня нет матчей')
