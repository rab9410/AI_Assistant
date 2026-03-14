import re
from datetime import datetime

import requests

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


def execute_tool_logic(tool_type, args):
    timeout = 10
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36"
        )
    }
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def extract_web_content(html):
        if HAS_BS4:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(
                ["script", "style", "nav", "footer",
                 "header", "aside", "form", "noscript", "iframe"]
            ):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
        else:
            html = re.sub(
                r"<(script|style|nav|footer|header)[^>]*>.*?",
                "",
                html,
                flags=re.DOTALL | re.IGNORECASE
            )
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
        return text[:2500]

    try:
        tool = tool_type.lower().strip()

        if tool == "weather":
            loc = (args.get("location", "Cape Town").strip() or "Cape Town")
            try:
                r = requests.get(
                    "https://wttr.in/"
                    f"{requests.utils.quote(loc)}?format=j1",
                    timeout=timeout,
                    headers=headers
                )
                r.raise_for_status()
                wd = r.json()
                cur = wd["current_condition"][0]
                area = wd["nearest_area"][0]
                area_nm = area["areaName"][0]["value"]
                country = area["country"][0]["value"]
                fc_lines = []
                for day in wd.get("weather", [])[:3]:
                    astro = day.get("astronomy", [{}])[0]
                    hourly = day.get("hourly", [])
                    mid = (
                        hourly[4]["weatherDesc"][0]["value"]
                        if len(hourly) > 4
                        else cur.get("weatherDesc", [{}])[0].get("value", "")
                    )
                    fc_lines.append(
                        f"  {day.get('date', '')}: {mid}, "
                        f"High {day.get('maxtempC', '?')}C/"
                        f"{day.get('maxtempF', '?')}F, "
                        f"Low {day.get('mintempC', '?')}C/"
                        f"{day.get('mintempF', '?')}F, "
                        f"Sunrise {astro.get('sunrise', 'N/A')}, "
                        f"Sunset {astro.get('sunset', 'N/A')}"
                    )
                return (
                    f"TOOL RESULT\ntool=weather\nsource=wttr.in\n"
                    f"timestamp={ts}\n"
                    f"location={area_nm}, {country}\n"
                    f"temperature={cur.get('temp_C', 'N/A')}°C / "
                    f"{cur.get('temp_F', 'N/A')}°F\n"
                    f"feels_like={cur.get('FeelsLikeC', 'N/A')}°C / "
                    f"{cur.get('FeelsLikeF', 'N/A')}°F\n"
                    f"condition={cur.get('weatherDesc', [{}])[0].get('value', 'N/A')}\n"
                    f"humidity={cur.get('humidity', 'N/A')}%\n"
                    f"wind={cur.get('windspeedKmph', 'N/A')} km/h "
                    f"{cur.get('winddir16Point', '')}\n"
                    f"visibility={cur.get('visibility', 'N/A')} km\n"
                    f"pressure={cur.get('pressure', 'N/A')} mb\n"
                    f"uv_index={cur.get('uvIndex', 'N/A')}\n"
                    f"3_day_forecast=\n" + "\n".join(fc_lines)
                )
            except Exception:
                try:
                    r2 = requests.get(
                        "https://wttr.in/"
                        f"{requests.utils.quote(loc)}"
                        "?format=%l|%C|%t|%h|%w",
                        timeout=timeout,
                        headers=headers
                    )
                    r2.raise_for_status()
                    p = r2.text.strip().split("|")
                    if len(p) >= 5 and "Unknown" not in r2.text:
                        return (
                            f"TOOL RESULT\ntool=weather\n"
                            f"source=wttr.in\ntimestamp={ts}\n"
                            f"location={p[0]}\n"
                            f"temperature={p[2]}\n"
                            f"condition={p[1]}\n"
                            f"humidity={p[3]}\nwind={p[4]}"
                        )
                except Exception:
                    pass
                return f"TOOL ERROR: Could not retrieve weather for '{loc}'."

        elif tool == "search":
            query = args.get("query", "").strip()
            if not query:
                return "TOOL ERROR: No search query provided."
            search_url = (
                "https://html.duckduckgo.com/html/"
                f"?q={requests.utils.quote(query)}"
            )

            def fetch_raw(url, proxy=False):
                try:
                    target = (
                        "https://api.allorigins.win/raw?"
                        f"url={requests.utils.quote(url)}"
                        if proxy else url
                    )
                    resp = requests.get(target, headers=headers, timeout=timeout)
                    if resp.status_code == 200:
                        return resp.text
                except Exception:
                    pass
                return None

            html_text = fetch_raw(search_url)
            if not html_text or "result__a" not in html_text:
                html_text = fetch_raw(search_url, proxy=True)
            if not html_text:
                return f"TOOL ERROR: Search unavailable for '{query}'."

            results = re.findall(
                r']*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]+)',
                html_text
            )
            snippets = re.findall(
                r']*class="result__snippet"[^>]*>(.*?)',
                html_text,
                re.DOTALL
            )
            gathered = []
            fetch_links = []
            for i in range(min(5, len(results))):
                link, title = results[i]
                if "uddg=" in link:
                    try:
                        link = requests.utils.unquote(
                            link.split("uddg=")[1].split("&")[0]
                        )
                    except Exception:
                        pass
                snip = (
                    re.sub("<[^<]+?>", "", snippets[i]).strip()
                    if i < len(snippets) else "No snippet."
                )
                gathered.append(
                    f"TITLE: {title}\nURL: {link}\nSUMMARY: {snip}"
                )
                if link.startswith("http"):
                    fetch_links.append(link)

            page_ctx = []
            for target_url in fetch_links[:2]:
                raw = fetch_raw(target_url) or fetch_raw(target_url, proxy=True)
                if raw:
                    extracted = extract_web_content(raw)
                    if len(extracted) > 100:
                        page_ctx.append(
                            f"--- CONTENT FROM {target_url} ---\n{extracted}"
                        )

            final = "\n\n".join(gathered)
            if page_ctx:
                final += "\n\n" + "\n\n".join(page_ctx)
            if not final.strip():
                return f"TOOL ERROR: No results for '{query}'."

            return (
                f"TOOL RESULT\ntool=search\nsource=Web\n"
                f"timestamp={ts}\nquery={query}\ndata=\n{final}"
            )

        elif tool == "market":
            ticker = args.get("ticker", "").upper().strip().replace("$", "")
            if not ticker:
                return "TOOL ERROR: No ticker provided."
            url = (
                "https://query1.finance.yahoo.com/v8/finance/chart/"
                f"{ticker}?interval=1m&range=1d"
            )
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            result_arr = r.json().get("chart", {}).get("result", [])
            if not result_arr:
                return f"TOOL ERROR: Ticker '{ticker}' returned no data."
            meta = result_arr[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            prev = meta.get("previousClose")
            currency = meta.get("currency", "USD")
            name = meta.get("longName") or meta.get("shortName") or ticker
            if not price:
                return f"TOOL ERROR: No price for '{ticker}'."
            change = round(price - prev, 4) if prev else "N/A"
            pct = (
                round((change / prev) * 100, 2)
                if prev and isinstance(change, float)
                else "N/A"
            )
            arrow = "▲" if isinstance(change, float) and change >= 0 else "▼"
            return (
                f"TOOL RESULT\ntool=market\nsource=Yahoo Finance\ntimestamp={ts}\n"
                f"name={name}\nticker={ticker}\n"
                f"exchange={meta.get('exchangeName', 'N/A')}\n"
                f"price={price} {currency}\n"
                f"change={arrow}{abs(change) if isinstance(change, float) else change} ({pct}%)\n"
                f"prev_close={prev}\n"
                f"day_high={meta.get('regularMarketDayHigh', 'N/A')}\n"
                f"day_low={meta.get('regularMarketDayLow', 'N/A')}\n"
                f"volume={meta.get('regularMarketVolume', 'N/A')}"
            )

        elif tool == "crypto":
            coin = (args.get("coin", "bitcoin").lower().strip() or "bitcoin")
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price"
                f"?ids={requests.utils.quote(coin)}"
                "&vs_currencies=usd,eur,zar"
                "&include_24hr_change=true"
                "&include_market_cap=true",
                timeout=timeout,
                headers=headers
            )
            r.raise_for_status()
            data = r.json().get(coin, {})
            if not data:
                return f"TOOL ERROR: Coin '{coin}' not found."
            ch = data.get("usd_24h_change")
            ch_str = f"{ch:.2f}%" if ch is not None else "N/A"
            return (
                f"TOOL RESULT\ntool=crypto\nsource=CoinGecko\ntimestamp={ts}\n"
                f"coin={coin}\n"
                f"price_usd=${data.get('usd', 'N/A'):,}\n"
                f"price_eur=€{data.get('eur', 'N/A'):,}\n"
                f"price_zar=R{data.get('zar', 'N/A'):,}\n"
                f"24h_change={ch_str}\n"
                f"market_cap_usd=${data.get('usd_market_cap', 'N/A'):,}"
            )

        elif tool == "currency":
            base = args.get("base", "USD").upper().strip()
            target = args.get("target", "ZAR").upper().strip()
            try:
                amount = float(args.get("amount", 1))
            except (ValueError, TypeError):
                amount = 1.0

            r = requests.get(
                f"https://api.exchangerate-api.com/v4/latest/{base}",
                timeout=timeout,
                headers=headers
            )
            r.raise_for_status()
            rate = r.json().get("rates", {}).get(target)
            if not rate:
                return f"TOOL ERROR: Cannot convert {base} to {target}."
            return (
                f"TOOL RESULT\ntool=currency\nsource=ExchangeRate-API\ntimestamp={ts}\n"
                f"base={base}\ntarget={target}\nrate={rate}\n"
                f"amount={amount} {base}\n"
                f"converted={round(amount * rate, 4)} {target}"
            )

        elif tool == "news":
            topic = args.get("topic", "top headlines").strip()
            country = args.get("country", "south africa").strip()
            return execute_tool_logic(
                "search",
                {"query": f"{topic} {country} news today"}
            )

        elif tool == "time":
            location = args.get("location", "").strip()
            q = f"current time in {location}" if location else "current UTC time"
            return execute_tool_logic("search", {"query": q})

        else:
            return f"TOOL ERROR: Unknown tool '{tool_type}'."

    except requests.exceptions.Timeout:
        return f"TOOL ERROR: Timed out for '{tool_type}'."
    except requests.exceptions.ConnectionError:
        return f"TOOL ERROR: No connection for '{tool_type}'."
    except Exception as e:
        return f"TOOL ERROR: {tool_type} — {str(e)}"