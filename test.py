import asyncio
import datetime
import time
from pprint import pprint

import aiohttp

from substitution_plan.parser import StudentSubstitutionParser, BaseSubstitutionParser, parse_next_site
from substitution_plan.utils import create_date_timestamp


async def load_result(num):
    print("loading result", num)
    #await asyncio.sleep(10-num)
    print("loaded result", num)
    return


"""async def load_site(session, num, stop):
    if num > stop:
        return

    async def load():
        global max_result_num

        async with session.get(f"https://gaw-verden.de/images/vertretung/klassen/subst_{num:03}.htm") as r:
            text = await r.text("iso-8859-1")
        print("got text for", num)
        results[num] = (load_result(num), num)
        if max_result_num+1 == num:
            max_result_num = num
            results_to_load = [results.pop(num)]
            while True:
                new_max_result_num = max_result_num + 1
                if new_max_result_num in results:
                    max_result_num = new_max_result_num
                    results_to_load.append(results.pop(max_result_num))
                else:
                    break
            print(num, "load results", [r[1] for r in results_to_load])
            await asyncio.gather(*(r[0] for r in results_to_load))
        if "subst_001.htm" in text:
            print("CANCEL", num)
            g.cancel()
        return True
    print("loading site", num)
    g = asyncio.gather(load(), load_site(session, num+1, stop))
    try:
        await g
    except asyncio.CancelledError:
        print(num, "was cancelled")"""





async def load_sites(session: aiohttp.ClientSession, num_start, num_stop):
    results = [None for _ in range(num_start, num_stop+1)]
    next_waiting_result = 1
    data = {}
    current_timestamp = create_date_timestamp(datetime.datetime.now())

    async def load(num):
        nonlocal next_waiting_result
        print("LOAD", num)
        r = await session.get(f"https://gaw-verden.de/images/vertretung/klassen/subst_{num:03}.htm")
        if r.status == 200:
            print("got request for", num)
            next_site = await parse_next_site(r.content)
            print("next site", next_site)
            if b"001" == next_site:
                print("CANCEL", num)
                for l in loads[num:]:
                    l.cancel()
            results[num-1] = r
            if next_waiting_result == num:
                results_to_load = [results[num-1]]
                next_waiting_result += 1
                while True:
                    try:
                        if results[next_waiting_result-1] is not None:
                            results_to_load.append(results[next_waiting_result-1])
                            next_waiting_result += 1
                        else:
                            break
                    except IndexError:
                        break
                print("num", num)
                print(results)
                print("loads results", results_to_load)
                await asyncio.wait([asyncio.ensure_future(parse_site(request, data, current_timestamp))
                                    for request in results_to_load])

    loads = [asyncio.ensure_future(load(num)) for num in range(num_start, num_stop+1)]
    await asyncio.wait(loads)
    for r in results[next_waiting_result:]:
        if r is not None:
            r[0].close()
    print(results)
    return data


async def main():
    async with aiohttp.ClientSession() as session:
        return await load_sites(session, 1, 8)

t1 = time.perf_counter_ns()
pprint(asyncio.run(main()))
t2 = time.perf_counter_ns()
print((t2-t1)/1e+9)
