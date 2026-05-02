!macro StopTranslatorSidecar executableName
  DetailPrint "Stopping ${executableName} if it is still running..."
  !if "${INSTALLMODE}" == "currentUser"
    nsis_tauri_utils::KillProcessCurrentUser "${executableName}"
  !else
    nsis_tauri_utils::KillProcess "${executableName}"
  !endif
  Pop $R0
  Sleep 500
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro StopTranslatorSidecar "translator-bridge.exe"
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro StopTranslatorSidecar "translator-bridge.exe"
!macroend
