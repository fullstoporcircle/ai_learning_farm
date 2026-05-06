@echo off
setlocal enabledelayedexpansion

set BASE_URL=http://localhost:5000
if not "%1"=="" set BASE_URL=%1

echo ============================================
echo  AI知识农场 - API 健康检查脚本
echo  目标: %BASE_URL%
echo ============================================
echo.

set PASS=0
set FAIL=0

echo [1/6] GET /api/health
curl -s -w "\nHTTP_STATUS: %%{http_code}\n" "%BASE_URL%/api/health" 2>nul
if %ERRORLEVEL%==0 (
    set /a PASS+=1
    echo [PASS] /api/health
) else (
    set /a FAIL+=1
    echo [FAIL] /api/health - 无法连接
)
echo.

echo [2/6] GET /api/farm
curl -s -w "\nHTTP_STATUS: %%{http_code}\n" "%BASE_URL%/api/farm" 2>nul
if %ERRORLEVEL%==0 (
    set /a PASS+=1
    echo [PASS] /api/farm
) else (
    set /a FAIL+=1
    echo [FAIL] /api/farm
)
echo.

echo [3/6] GET /api/backpack
curl -s -w "\nHTTP_STATUS: %%{http_code}\n" "%BASE_URL%/api/backpack" 2>nul
if %ERRORLEVEL%==0 (
    set /a PASS+=1
    echo [PASS] /api/backpack
) else (
    set /a FAIL+=1
    echo [FAIL] /api/backpack
)
echo.

echo [4/6] POST /api/extract (with sample text)
curl -s -w "\nHTTP_STATUS: %%{http_code}\n" -X POST -H "Content-Type: application/json" -d "{\"text\":\"感知机是最简单的神经网络模型，它由Frank Rosenblatt于1957年提出。感知机接收多个输入信号，产生一个输出信号。其数学公式为 y = f(w*x + b)，其中w是权重，b是偏置。\"}" "%BASE_URL%/api/extract" 2>nul
if %ERRORLEVEL%==0 (
    set /a PASS+=1
    echo [PASS] /api/extract
) else (
    set /a FAIL+=1
    echo [FAIL] /api/extract
)
echo.

echo [5/6] GET /api/review_plan
curl -s -w "\nHTTP_STATUS: %%{http_code}\n" "%BASE_URL%/api/review_plan" 2>nul
if %ERRORLEVEL%==0 (
    set /a PASS+=1
    echo [PASS] /api/review_plan
) else (
    set /a FAIL+=1
    echo [FAIL] /api/review_plan
)
echo.

echo [6/6] GET /api/farm_summary
curl -s -w "\nHTTP_STATUS: %%{http_code}\n" "%BASE_URL%/api/farm_summary" 2>nul
if %ERRORLEVEL%==0 (
    set /a PASS+=1
    echo [PASS] /api/farm_summary
) else (
    set /a FAIL+=1
    echo [FAIL] /api/farm_summary
)
echo.

echo ============================================
echo  测试结果: %PASS% 通过, %FAIL% 失败
echo ============================================

if %FAIL% GTR 0 (
    echo.
    echo 排查建议:
    echo 1. 确认后端服务已启动: python app.py
    echo 2. 检查 .env 文件是否存在且配置正确
    echo 3. 检查数据库文件 farm.db 是否可写
    echo 4. 查看后端控制台日志是否有报错
)

endlocal
