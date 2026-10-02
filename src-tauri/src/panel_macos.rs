// The quick window as a non-activating panel, the kind Spotlight uses. It
// takes the keyboard without making Translator the active app, so showing it
// leaves the main window where it is (activating the app would bring that
// forward too), and hiding it hands the keyboard straight back to the app the
// text was copied from.

use std::sync::OnceLock;

use objc2::runtime::{AnyClass, AnyObject, Bool, ClassBuilder, Sel};
use objc2::sel;
use objc2_app_kit::{NSPanel, NSWindowCollectionBehavior, NSWindowStyleMask};

extern "C-unwind" fn can_become_key(_: &AnyObject, _: Sel) -> Bool {
    Bool::YES
}

// tao's window class adds one field, `focusable`; the panel class declares the
// same field so the window keeps its layout when it changes class.
fn panel_class() -> Option<&'static AnyClass> {
    static CLASS: OnceLock<Option<&'static AnyClass>> = OnceLock::new();
    *CLASS.get_or_init(|| {
        let mut builder = ClassBuilder::new(c"TranslatorQuickPanel", AnyClass::get(c"NSPanel")?)?;
        builder.add_ivar::<Bool>(c"focusable");
        unsafe {
            builder.add_method(
                sel!(canBecomeKeyWindow),
                can_become_key as extern "C-unwind" fn(_, _) -> _,
            );
        }
        Some(builder.register())
    })
}

fn focusable_offset(class: &AnyClass) -> Option<isize> {
    class.instance_variable(c"focusable").map(|ivar| ivar.offset())
}

// Turns the window into a panel. Must run on the main thread. Returns false,
// leaving the window as it was, when its layout is not the one expected.
pub fn make_panel(window: &tauri::WebviewWindow) -> bool {
    let Some(class) = panel_class() else {
        return false;
    };
    let Ok(pointer) = window.ns_window() else {
        return false;
    };
    let object = unsafe { &*(pointer as *const AnyObject) };
    let current = object.class();
    if current.instance_size() != class.instance_size()
        || focusable_offset(current) != focusable_offset(class)
    {
        return false;
    }
    unsafe { AnyObject::set_class(object, class) };

    let panel = unsafe { &*(pointer as *const NSPanel) };
    panel.setStyleMask(panel.styleMask() | NSWindowStyleMask::NonactivatingPanel);
    panel.setFloatingPanel(true);
    panel.setBecomesKeyOnlyIfNeeded(false);
    // Translator is usually not the active app while the panel is up.
    panel.setHidesOnDeactivate(false);
    panel.setCanHide(false);
    // Opens on the space the user is on, full-screen apps included.
    panel.setCollectionBehavior(
        panel.collectionBehavior()
            | NSWindowCollectionBehavior::MoveToActiveSpace
            | NSWindowCollectionBehavior::FullScreenAuxiliary,
    );
    true
}
