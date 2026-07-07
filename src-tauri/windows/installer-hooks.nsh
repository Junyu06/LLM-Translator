Function WaitForTranslatorBridgeExit
  DetailPrint "Waiting for translator-bridge.exe to exit..."
  StrCpy $R0 0

  wait_translator_bridge_loop:
    nsExec::ExecToStack 'cmd /C tasklist /FI "IMAGENAME eq translator-bridge.exe" | find /I "translator-bridge.exe" >NUL'
    Pop $R1
    Pop $R2
    IntCmp $R1 0 wait_translator_bridge_running wait_translator_bridge_done wait_translator_bridge_done

  wait_translator_bridge_running:
    IntOp $R0 $R0 + 1
    IntCmp $R0 20 wait_translator_bridge_timeout 0 0
    Sleep 250
    Goto wait_translator_bridge_loop

  wait_translator_bridge_timeout:
    DetailPrint "translator-bridge.exe still running after bounded wait; continuing installer."
    Goto wait_translator_bridge_end

  wait_translator_bridge_done:
    DetailPrint "translator-bridge.exe is not running."

  wait_translator_bridge_end:
FunctionEnd

!macro NSIS_HOOK_PREINSTALL
  Call WaitForTranslatorBridgeExit
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  Call WaitForTranslatorBridgeExit
!macroend
