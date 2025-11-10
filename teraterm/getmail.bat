
@echo off
setlocal

:: Nhận biến server_sel từ tham số đầu tiên
set server_sel=%1

:: Gán chuỗi kết nối SQL tùy theo server
if "%server_sel%"=="0" (
    set SQL_CONNECT=sqlplus -S MU_NRI/NRI@localhost:1521/ORCL
) else if "%server_sel%"=="1" (
    set SQL_CONNECT=sqlplus -S MU_NRI01/NRI@localhost:1521/ORCL
) else if "%server_sel%"=="2" (
    set SQL_CONNECT=sqlplus -S MU_NRI02/NRI@localhost:1521/ORCL
) else if "%server_sel%"=="3" (
    set SQL_CONNECT=sqlplus -S MU_NRI03/NRI@localhost:1521/ORCL
) else if "%server_sel%"=="4" (
    set SQL_CONNECT=sqlplus -S MU_NRI04/NRI@localhost:1521/ORCL
) else if "%server_sel%"=="5" (
    set SQL_CONNECT=sqlplus -S MU_NRI05/NRI@localhost:1521/ORCL
) else (
    echo [Lỗi] Không hợp lệ hoặc không truyền tham số server_sel!
    goto :EOF
)

set SQL_FILE=%TEMP%\query.sql
(
    echo SET PAGESIZE 10;
    echo SET LINESIZE 50;
    echo SET FEEDBACK OFF;
    echo SET VERIFY OFF;
    echo SET HEADING ON;
    echo SET ECHO OFF;
    echo PROMPT;
    echo SELECT DISTINCT(KOMOKU_NM_1^) AS MAIL_INFO FROM M_HANYO mh WHERE KOMOKU_NM_1 LIKE '%%@%%';
    rem Không có EXIT để giữ prompt mở
) > "%SQL_FILE%"
cls
:: Mở sqlplus và chạy file query.sql, giữ cửa sổ mở
start cmd /k "%SQL_CONNECT% @%SQL_FILE%"

endlocal
