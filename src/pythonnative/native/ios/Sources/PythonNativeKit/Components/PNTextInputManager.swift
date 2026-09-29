import UIKit

/// `TextInput`: a single-line `UITextField` or multiline `UITextView`.
///
/// The class is chosen at creation from the `multiline` prop. Programmatic
/// `value` updates set a suppress flag so they don't echo into `on_change`.
public final class PNTextInputManager: PNComponentManager {
    public override func makeView(props: [String: Any]) -> UIView {
        if PNProps.bool(PNProps.value(props, "multiline")) == true {
            let view = UITextView(frame: .zero)
            view.font = UIFont.systemFont(ofSize: 17)
            view.backgroundColor = .white
            return view
        }
        let field = UITextField(frame: .zero)
        field.borderStyle = .roundedRect
        return field
    }

    public override func createView(tag: Int64, props: [String: Any]) -> UIView {
        let view = super.createView(tag: tag, props: props)
        let delegate = PNTextInputDelegate(view: view)
        PNViewState.existing(for: view)?.retained.append(delegate)
        if let field = view as? UITextField {
            field.delegate = delegate
            field.addTarget(delegate, action: #selector(PNTextInputDelegate.editingChanged(_:)), for: .editingChanged)
            field.addTarget(delegate, action: #selector(PNTextInputDelegate.editingDidEndOnExit(_:)), for: .editingDidEndOnExit)
        } else if let textView = view as? UITextView {
            textView.delegate = delegate
        }
        return view
    }

    public override func apply(view: UIView, props: [String: Any], initial: Bool) {
        let typed = try! TextInputProps(props, validated: true)

        guard let state = PNViewState.existing(for: view) else { return }
        let field = view as? UITextField
        let textView = view as? UITextView
        if typed.has_max_length {
            state.extras["max_length"] = typed.max_length.map { Int($0) } as Any? ?? NSNull()
        }
        if let value = typed.value {
            let current = field?.text ?? textView?.text ?? ""
            let acknowledged = PNProps.int(props["_pn_edit_revision"]) ?? 0
            let edited = state.extras["edit_revision"] as? Int ?? 0
            if current != value && acknowledged >= edited {
                if (view as? UITextInput)?.markedTextRange != nil {
                    state.extras["pending_value"] = ["value": value, "revision": acknowledged]
                } else {
                    state.extras.removeValue(forKey: "pending_value")
                    PNTextInputManager.setText(view, value)
                }
            }
        }
        if let field = field {
            if typed.has_placeholder {
                field.placeholder = typed.placeholder ?? ""
            }
            if let color = PNColor.parse(PNProps.value(props, "placeholder_color")) {
                let placeholder = PNProps.string(PNProps.value(state.props, "placeholder")) ?? ""
                field.attributedPlaceholder = NSAttributedString(string: placeholder, attributes: [.foregroundColor: color])
            }
            if typed.has_clear_button {
                field.clearButtonMode = typed.clear_button == true ? .whileEditing : .never
            }
        }
        if initial || PNTextManager.fontKeys.contains(where: { PNProps.has(props, $0) }) {
            let font = PNTextManager.font(from: state.props, base: nil)
            field?.font = font
            textView?.font = font
            field?.adjustsFontForContentSizeCategory = true
            textView?.adjustsFontForContentSizeCategory = true
        }
        if let color = PNColor.parse(PNProps.value(props, "color")) {
            field?.textColor = color
            textView?.textColor = color
        }
        if let color = PNColor.parse(PNProps.value(props, "background_color")) {
            view.backgroundColor = color
        }
        if typed.has_secure {
            let secure = typed.secure ?? false
            field?.isSecureTextEntry = secure
            textView?.isSecureTextEntry = secure
        }
        if let keyboard = typed.keyboard_type?.rawValue {
            let type = PNTextInputManager.keyboardType(keyboard)
            field?.keyboardType = type
            textView?.keyboardType = type
            if keyboard == "visible_password" {
                // A visible password is the default keyboard with masking off.
                field?.isSecureTextEntry = false
                textView?.isSecureTextEntry = false
            }
        }
        if let appearance = typed.keyboard_appearance?.rawValue {
            let value = PNTextInputManager.keyboardAppearance(appearance)
            field?.keyboardAppearance = value
            textView?.keyboardAppearance = value
        }
        if typed.has_selection {
            // Controlled selection: apply the requested range once per change
            // and let the user move the caret freely afterwards.
            if let selection = typed.selection {
                let start = Int(selection.start), end = Int(max(selection.start, selection.end))
                if PNTextInputManager.currentSelection(view).map({ $0 != (start, end) }) ?? true {
                    PNTextInputManager.setSelection(view, start: start, end: end)
                }
                state.extras["controlled_selection"] = [start, end]
            } else {
                state.extras.removeValue(forKey: "controlled_selection")
            }
        }
        if let cap = typed.auto_capitalize?.rawValue {
            let type = PNTextInputManager.capitalization(cap)
            field?.autocapitalizationType = type
            textView?.autocapitalizationType = type
        }
        if typed.has_auto_correct {
            let type: UITextAutocorrectionType = typed.auto_correct == true ? .yes : .no
            field?.autocorrectionType = type
            textView?.autocorrectionType = type
        }
        if let key = typed.return_key_type?.rawValue {
            let type = PNTextInputManager.returnKey(key)
            field?.returnKeyType = type
            textView?.returnKeyType = type
        }
        if let color = PNColor.parse(PNProps.value(props, "selection_color")) {
            view.tintColor = color
        }
        if typed.has_text_content_type {
            let type = typed.text_content_type.flatMap(PNTextInputManager.contentType)
            field?.textContentType = type
            textView?.textContentType = type
        }
        if typed.has_editable {
            let editable = typed.editable ?? true
            field?.isEnabled = editable
            textView?.isEditable = editable
        }
        if typed.auto_focus == true {
            view.becomeFirstResponder()
        }
        PNViewStyler.applyDecoration(view, props)
    }

    public override func measure(view: UIView, maxW: CGFloat, maxH: CGFloat) -> CGSize {
        let size = super.measure(view: view, maxW: maxW, maxH: maxH)
        return CGSize(width: max(size.width, 100), height: max(size.height, 36))
    }

    public override func command(view: UIView, name: String, args: [String: Any]) -> Any? {
        switch name {
        case "focus":
            view.becomeFirstResponder()
        case "blur":
            view.resignFirstResponder()
        case "clear":
            PNTextInputManager.setText(view, "")
            // `clear()` is an edit: report it so a controlled value follows,
            // as Android's text watcher and the browser do.
            PNEvents.emitIfWired(view, "on_change", [""])
        case "get_value":
            return (view as? UITextField)?.text ?? (view as? UITextView)?.text ?? ""
        case "select_all":
            (view as? UITextField)?.selectAll(nil)
            (view as? UITextView)?.selectAll(nil)
        case "set_selection":
            if let start = PNProps.int(args["start"]) {
                let end = PNProps.int(args["end"]) ?? start
                PNTextInputManager.setSelection(view, start: start, end: end)
            }
        default:
            break
        }
        return nil
    }

    // MARK: - Helpers

    static func scheduleCompositionFlush(_ view: UIView) {
        guard let state = PNViewState.existing(for: view), state.extras["pending_value"] != nil,
              !state.flag("composition_flush") else { return }
        state.extras["composition_flush"] = true
        DispatchQueue.main.async { [weak view] in
            guard let view = view, let state = PNViewState.existing(for: view) else { return }
            state.extras["composition_flush"] = false
            flushComposition(view)
        }
    }

    static func flushComposition(_ view: UIView) {
        guard (view as? UITextInput)?.markedTextRange == nil, let state = PNViewState.existing(for: view),
              let pending = state.extras.removeValue(forKey: "pending_value") as? [String: Any],
              let revision = pending["revision"] as? Int,
              revision >= (state.extras["edit_revision"] as? Int ?? 0), let value = pending["value"] as? String else { return }
        setText(view, value)
        PNLayout.invalidate(state.tag)
    }

    static func setText(_ view: UIView, _ text: String) {
        guard let state = PNViewState.existing(for: view) else { return }
        let input = view as? UITextInput
        let selection = input?.selectedTextRange
        let start = selection.flatMap { range in input.map { $0.offset(from: $0.beginningOfDocument, to: range.start) } } ?? 0
        let end = selection.flatMap { range in input.map { $0.offset(from: $0.beginningOfDocument, to: range.end) } } ?? start
        state.extras["suppress"] = true
        (view as? UITextField)?.text = text
        if let textView = view as? UITextView {
            // Complete any pending correction in the old document before
            // replacing it. Otherwise UIKit can apply it to the new value.
            textView.selectedRange = NSRange(location: 0, length: textView.text.utf16.count)
            // Typing attributes can contain IME annotations after unmarking.
            // A controlled value inherits visual styling, never those edits.
            let paragraph = NSMutableParagraphStyle()
            paragraph.alignment = textView.textAlignment
            textView.attributedText = NSAttributedString(string: text, attributes: [
                .font: textView.font ?? UIFont.systemFont(ofSize: 17),
                .foregroundColor: textView.textColor ?? UIColor.label,
                .paragraphStyle: paragraph,
            ])
        }
        setSelection(view, start: min(start, text.utf16.count), end: min(end, text.utf16.count))
        state.extras["suppress"] = false
    }

    static func setSelection(_ view: UIView, start: Int, end: Int) {
        if let textView = view as? UITextView {
            let length = textView.text.utf16.count
            guard start >= 0, end >= start, end <= length else { return }
            textView.selectedRange = NSRange(location: start, length: end - start)
            return
        }
        guard let input = view as? UITextInput else { return }
        let begin = input.beginningOfDocument
        guard let from = input.position(from: begin, offset: start),
              let to = input.position(from: begin, offset: end)
        else { return }
        input.selectedTextRange = input.textRange(from: from, to: to)
    }

    static func keyboardType(_ name: String) -> UIKeyboardType {
        switch name {
        case "ascii": return .asciiCapable
        case "numbers_and_punctuation": return .numbersAndPunctuation
        case "url": return .URL
        case "number_pad", "numeric": return .numberPad
        case "phone_pad": return .phonePad
        case "email_address", "email": return .emailAddress
        case "decimal_pad", "decimal": return .decimalPad
        case "web_search": return .webSearch
        case "visible_password": return .default
        default: return .default
        }
    }

    static func keyboardAppearance(_ name: String) -> UIKeyboardAppearance {
        switch name {
        case "light": return .light
        case "dark": return .dark
        default: return .default
        }
    }

    /// The current `(start, end)` selection in UTF-16 offsets.
    static func currentSelection(_ view: UIView) -> (Int, Int)? {
        guard let input = view as? UITextInput, let range = input.selectedTextRange else { return nil }
        return (input.offset(from: input.beginningOfDocument, to: range.start), input.offset(from: input.beginningOfDocument, to: range.end))
    }

    /// `blur_on_submit` resolved against its default: single-line inputs
    /// blur on return, multiline ones insert a newline.
    static func blursOnSubmit(_ props: [String: Any], multiline: Bool) -> Bool {
        if let explicit = PNProps.bool(PNProps.value(props, "blur_on_submit")) { return explicit }
        return !multiline
    }

    /// `on_key_press` key name for replacing `range` with `replacement`,
    /// or `nil` when the change isn't a keystroke. UIKit sends an empty
    /// replacement over an empty range when it commits or unmarks text
    /// (for example as the field ends editing); only an empty replacement
    /// that deletes something is a Backspace.
    static func keyName(for replacement: String, range: NSRange) -> String? {
        if replacement.isEmpty { return range.length > 0 ? "Backspace" : nil }
        return keyName(for: replacement)
    }

    /// `on_key_press` key name for a non-empty replacement string.
    static func keyName(for replacement: String) -> String {
        if replacement.isEmpty { return "Backspace" }
        if replacement == "\n" || replacement == "\r" { return "Enter" }
        return replacement
    }

    static func capitalization(_ name: String) -> UITextAutocapitalizationType {
        switch name {
        case "none": return .none
        case "words": return .words
        case "characters": return .allCharacters
        default: return .sentences
        }
    }

    static func returnKey(_ name: String) -> UIReturnKeyType {
        switch name {
        case "go": return .go
        case "google": return .google
        case "join": return .join
        case "next": return .next
        case "route": return .route
        case "search": return .search
        case "send": return .send
        case "yahoo": return .yahoo
        case "done": return .done
        default: return .default
        }
    }

    static func contentType(_ name: String) -> UITextContentType? {
        switch name.trimmingCharacters(in: .whitespaces).lowercased() {
        case "username": return .username
        case "password": return .password
        case "new_password": return .newPassword
        case "one_time_code": return .oneTimeCode
        case "email", "email_address": return .emailAddress
        case "name": return .name
        case "url": return .URL
        case "telephone", "telephone_number", "phone", "phone_number": return .telephoneNumber
        default: return nil
        }
    }
}

/// Delegate and control target for both input classes.
final class PNTextInputDelegate: NSObject, UITextFieldDelegate, UITextViewDelegate {
    private weak var view: UIView?

    init(view: UIView) {
        self.view = view
    }

    private func currentText() -> String {
        (view as? UITextField)?.text ?? (view as? UITextView)?.text ?? ""
    }

    private func emitChange() {
        guard let view = view, let state = PNViewState.existing(for: view), !state.flag("suppress") else { return }
        PNTextInputManager.scheduleCompositionFlush(view)
        var text = currentText()
        if let maxLength = state.extras["max_length"] as? Int, maxLength >= 0, (view as? UITextInput)?.markedTextRange == nil, text.utf16.count > maxLength {
            var units = Array(text.utf16.prefix(maxLength))
            if let last = units.last, (0xD800...0xDBFF).contains(last) { units.removeLast() }
            text = String(decoding: units, as: UTF16.self)
            PNTextInputManager.setText(view, text)
        }
        PNEvents.emit(view, "on_change", [text])
        PNLayout.invalidate(state.tag)
    }

    private func emitSelection() {
        guard let view = view, let state = PNViewState.existing(for: view), state.hasEvent("on_selection_change"),
              let (start, end) = PNTextInputManager.currentSelection(view)
        else { return }
        if let last = state.extras["last_selection"] as? [Int], last == [start, end] { return }
        state.extras["last_selection"] = [start, end]
        PNComponentEvents.TextInput.on_selection_change(view, PNSelectionEvent(start: Int64(start), end: Int64(end)))
    }

    private func emitKeyPress(_ replacement: String, range: NSRange) {
        guard let view = view, let state = PNViewState.existing(for: view), state.hasEvent("on_key_press") else { return }
        // Pasting several characters reports each one, like React Native.
        if replacement.isEmpty || replacement.count == 1 || replacement == "\r\n" {
            guard let key = PNTextInputManager.keyName(for: replacement, range: range) else { return }
            PNComponentEvents.TextInput.on_key_press(view, PNKeyPressEvent(key: key))
        } else {
            for character in replacement {
                PNComponentEvents.TextInput.on_key_press(view, PNKeyPressEvent(key: PNTextInputManager.keyName(for: String(character))))
            }
        }
    }

    private func emitContentSize(_ textView: UITextView) {
        guard let view = view, let state = PNViewState.existing(for: view), state.hasEvent("on_content_size_change") else { return }
        let size = textView.contentSize
        let rounded = [Double(size.width), Double(size.height)]
        if let last = state.extras["last_content_size"] as? [Double], last == rounded { return }
        state.extras["last_content_size"] = rounded
        PNComponentEvents.TextInput.on_content_size_change(view, PNContentSizeEvent(width: rounded[0], height: rounded[1]))
    }

    private func selectAllIfRequested() {
        guard let view = view, let props = PNViewState.existing(for: view)?.props,
              PNProps.bool(PNProps.value(props, "select_text_on_focus")) == true else { return }
        DispatchQueue.main.async { [weak view] in
            (view as? UITextField)?.selectAll(nil)
            (view as? UITextView)?.selectAll(nil)
        }
    }

    // MARK: UITextField

    @objc func editingChanged(_ sender: Any?) {
        emitChange()
    }

    @objc func editingDidEndOnExit(_ sender: Any?) {
        guard let view = view else { return }
        PNEvents.emit(view, "on_submit", [currentText()])
    }

    func textFieldShouldReturn(_ textField: UITextField) -> Bool {
        // A single-line field never sees Return as a replacement string;
        // report it here like the multiline, Android, and browser inputs do.
        emitKeyPress("\n", range: NSRange(location: textField.text?.utf16.count ?? 0, length: 0))
        if PNTextInputManager.blursOnSubmit(PNViewState.existing(for: textField)?.props ?? [:], multiline: false) {
            textField.resignFirstResponder()
        }
        return true
    }

    func textField(_ textField: UITextField, shouldChangeCharactersIn range: NSRange, replacementString string: String) -> Bool {
        emitKeyPress(string, range: range)
        return true
    }

    func textFieldDidBeginEditing(_ textField: UITextField) {
        if let view = view { PNEvents.emit(view, "on_focus") }
        selectAllIfRequested()
    }

    func textFieldDidEndEditing(_ textField: UITextField) {
        if let view = view { PNEvents.emit(view, "on_blur") }
    }

    func textFieldDidChangeSelection(_ textField: UITextField) {
        if let view = view { PNTextInputManager.scheduleCompositionFlush(view) }
        emitSelection()
    }

    // MARK: UITextView

    func textViewDidChange(_ textView: UITextView) {
        emitChange()
        emitContentSize(textView)
    }

    func textView(_ textView: UITextView, shouldChangeTextIn range: NSRange, replacementText text: String) -> Bool {
        emitKeyPress(text, range: range)
        if text == "\n", let view = view,
           PNTextInputManager.blursOnSubmit(PNViewState.existing(for: view)?.props ?? [:], multiline: true) {
            PNComponentEvents.TextInput.on_submit(view, textView.text ?? "")
            textView.resignFirstResponder()
            return false
        }
        return true
    }

    func textViewDidBeginEditing(_ textView: UITextView) {
        if let view = view { PNEvents.emit(view, "on_focus") }
        selectAllIfRequested()
    }

    func textViewDidEndEditing(_ textView: UITextView) {
        if let view = view { PNEvents.emit(view, "on_blur") }
    }

    func textViewDidChangeSelection(_ textView: UITextView) {
        if let view = view { PNTextInputManager.scheduleCompositionFlush(view) }
        emitSelection()
    }
}
