## Test Description

> Test command
```
python3 -m unittest ./MainTest.py
python3 -m unittest ./AclientTest.py
```
In the output of `AclientTest.py`,

* The yellow text
  - means use `getenv()` to obtain `.env` information for testing
* The blue text
  - means use **Mock** for testing

> Code coverage command
```
coverage run -m unittest ./MainTest.py
coverage report
***********************************************
coverage run -m unittest ./AclientTest.py
coverage report
```

## Test Case
* `MainTest.py` :  2 cases
* `AclientTest.py` : 40 cases

## Note

Since `AclientTest.py` will test environment variables `.env`. <br>
So if want to run `AclientTest.py`, please fill in the necessary options of `.env` first

## Code Coverage
> `aclient.py` is **100%**
```
Name                            Stmts   Miss  Cover
---------------------------------------------------
/work/auto_login/AutoLogin.py     113     87    23%
/work/src/__init__.py               0      0   100%
/work/src/aclient.py              157      0   100%
/work/src/log.py                   35     16    54%
/work/src/personas.py               2      0   100%
/work/src/responses.py             33     26    21%
---------------------------------------------------
TOTAL                             340    129    62%
```

> `main.py` is **100%**
```
Name                            Stmts   Miss  Cover
---------------------------------------------------
/work/auto_login/AutoLogin.py     113     87    23%
/work/main.py                      17      0   100%
/work/src/__init__.py               0      0   100%
/work/src/aclient.py              157    102    35%
/work/src/art.py                   38     26    32%
/work/src/bot.py                  205    195     5%
/work/src/log.py                   35      9    74%
/work/src/personas.py               2      0   100%
/work/src/responses.py             33     26    21%
---------------------------------------------------
TOTAL                             600    445    26%
```