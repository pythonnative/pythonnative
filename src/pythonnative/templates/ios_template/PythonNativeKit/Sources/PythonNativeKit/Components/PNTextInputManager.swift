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
        guard let state = PNViewState.existing(for: view) else { return }
        let field = view as? UITextField
        let textView = view as? UITextView
        if PNProps.has(props, "max_length") {
            state.extras["max_length"] = PNProps.int(PNProps.value(props, "max_length")) as Any? ?? NSNull()
        }
        if let value = PNProps.string(PNProps.value(props, "value")) {
            let current = field?.text ?? textView?.text ?? ""
            if current != value {
                PNTextInputManager.setText(view, value)
            }
        }
        if let field = field {
            if PNProps.has(props, "placeholder") {
                field.placeholder = PNProps.string(PNProps.value(props, "placeholder")) ?? ""
            }
            if let color = PNColor.parse(PNProps.value(props, "placeholder_color")) {
                let placeholder = PNProps.string(PNProps.value(state.props, "placeholder")) ?? ""
                field.attributedPlaceholder = NSAttributedString(string: placeholder, attributes: [.foregroundColor: color])
            }
            if PNProps.has(props, "clear_button") {
                field.clearButtonMode = PNProps.bool(PNProps.value(props, "clear_button")) == true ? .whileEditing : .never
            }
        }
        if let size = PNProps.double(PNProps.value(props, "font_size")) {
            let font = UIFont.systemFont(ofSize: CGFloat(size))
            field?.font = font
            textView?.font = font
        }
        if let color = PNColor.parse(PNProps.value(props, "color")) {
            field?.textColor = color
            textView?.textColor = color
        }
        if let color = PNColor.parse(PNProps.value(props, "background_color")) {
            view.backgroundColor = color
        }
        if PNProps.has(props, "secure") {
            let secure = PNProps.bool(PNProps.value(props, "secure")) ?? false
            field?.isSecureTextEntry = secure
            textView?.isSecureTextEntry = secure
        }
        if let keyboard = PNProps.string(PNProps.value(props, "keyboard_type")) {
            let type = PNTextInputManager.keyboardType(keyboard)
            field?.keyboardType = type
            textView?.keyboardType = type
        }
        if let cap = PNProps.string(PNProps.value(props, "auto_capitalize")) {
            let type = PNTextInputManager.capitalization(cap)
            field?.autocapitalizationType = type
            textView?.autocapitalizationType = type
        }
        if PNProps.has(props, "auto_correct") {
            let type: UITextAutocorrectionType = PNProps.bool(PNProps.value(props, "auto_correct")) == true ? .yes : .no
            field?.autocorrectionType = type
            textView?.autocorrectionType = type
        }
        if let key = PNProps.string(PNProps.value(props, "return_key_type")) {
            let type = PNTextInputManager.returnKey(key)
            field?.returnKeyType = type
            textView?.returnKeyType = type
        }
        if let color = PNColor.parse(PNProps.value(props, "selection_color")) {
            view.tintColor = color
        }
        if PNProps.has(props, "text_content_type") {
            let type = PNProps.string(PNProps.value(props, "text_content_type")).flatMap(PNTextInputManager.contentType)
            field?.textContentType = type
            textView?.textContentType = type
        }
        if PNProps.has(props, "editable") {
            let editable = PNProps.bool(PNProps.value(props, "editable")) ?? true
            field?.isEnabled = editable
            textView?.isEditable = editable
        }
        if PNProps.bool(PNProps.value(props, "auto_focus")) == true {
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
        case "get_value":
            return (view as? UITextField)?.text ?? (view as? UITextView)?.text ?? ""
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

    static func setText(_ view: UIView, _ text: String) {
        guard let state = PNViewState.existing(for: view) else { return }
        state.extras["suppress"] = true
        (view as? UITextField)?.text = text
        (view as? UITextView)?.text = text
        state.extras["suppress"] = false
    }

    static func setSelection(_ view: UIView, start: Int, end: Int) {
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
        default: return .default
        }
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
        var text = currentText()
        if let maxLength = state.extras["max_length"] as? Int, maxLength >= 0, text.count > maxLength {
            text = String(text.prefix(maxLength))
            PNTextInputManager.setText(view, text)
        }
        PNEvents.emit(view, "on_change", [text])
    }

    private func emitSelection() {
        guard let view = view, let state = PNViewState.existing(for: view), state.hasEvent("on_selection_change"),
              let input = view as? UITextInput, let range = input.selectedTextRange
        else { return }
        let start = input.offset(from: input.beginningOfDocument, to: range.start)
        let end = input.offset(from: input.beginningOfDocument, to: range.end)
        PNEvents.emit(view, "on_selection_change", [["start": start, "end": end]])
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
        textField.resignFirstResponder()
        return true
    }

    func textFieldDidBeginEditing(_ textField: UITextField) {
        if let view = view { PNEvents.emit(view, "on_focus") }
    }

    func textFieldDidEndEditing(_ textField: UITextField) {
        if let view = view { PNEvents.emit(view, "on_blur") }
    }

    func textFieldDidChangeSelection(_ textField: UITextField) {
        emitSelection()
    }

    // MARK: UITextView

    func textViewDidChange(_ textView: UITextView) {
        emitChange()
    }

    func textViewDidBeginEditing(_ textView: UITextView) {
        if let view = view { PNEvents.emit(view, "on_focus") }
    }

    func textViewDidEndEditing(_ textView: UITextView) {
        if let view = view { PNEvents.emit(view, "on_blur") }
    }

    func textViewDidChangeSelection(_ textView: UITextView) {
        emitSelection()
    }
}
