' AI 英语刷题机 - 局域网模式启动器
' 双击运行：手机与电脑同一 WiFi 时，手机浏览器访问 http://本机IP:8765 即可刷题
' 首次使用请先给防火墙放行 8765 端口（见桌面说明.txt）

Set WshShell = CreateObject("WScript.Shell")
projectDir = "D:\english-multiple-choice-practice-machine"

' 后端未运行则启动（局域网模式绑定 0.0.0.0）
WshShell.CurrentDirectory = projectDir
WshShell.Run "pythonw run_app.py --lan", 0, False

' 等待就绪
ready = False
For i = 1 To 80
    WScript.Sleep 250
    On Error Resume Next
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.open "GET", "http://127.0.0.1:8765/api/health", False
    http.send
    If http.status = 200 Then
        ready = True
        Exit For
    End If
    On Error GoTo 0
Next

If ready Then
    ' 获取本机 IP 显示给用户
    Dim fso, tf, cmd, ip
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set tf = fso.CreateTextFile(projectDir & "\tmp_ip.bat", True)
    tf.WriteLine "@echo off"
    tf.WriteLine "for /f ""tokens=2 delims=:"" %%a in ('ipconfig ^| findstr ""IPv4""') do @echo %%a > """ & projectDir & "\tmp_ip.txt"""
    tf.Close
    WshShell.Run projectDir & "\tmp_ip.bat", 0, True
    On Error Resume Next
    Set tf = fso.OpenTextFile(projectDir & "\tmp_ip.txt", 1)
    ip = Trim(tf.ReadLine())
    tf.Close
    fso.DeleteFile projectDir & "\tmp_ip.bat"
    fso.DeleteFile projectDir & "\tmp_ip.txt"
    On Error GoTo 0

    MsgBox "刷题机已启动（局域网模式）" & vbCrLf & vbCrLf & _
        "手机操作（需与电脑同一 WiFi）：" & vbCrLf & _
        "1. 手机浏览器打开: http://" & ip & ":8765" & vbCrLf & _
        "2. 菜单 → 添加到主屏幕，即可当 App 用" & vbCrLf & vbCrLf & _
        "电脑本机: http://127.0.0.1:8765", 64, "AI 英语刷题机"
    WshShell.Run "http://127.0.0.1:8765", 1, False
Else
    MsgBox "启动超时，请检查依赖是否安装", 48, "AI 英语刷题机"
End If
