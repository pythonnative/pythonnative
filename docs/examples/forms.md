# Forms

A sign-up form with controlled inputs, basic validation, and a submit
handler. Demonstrates [`TextInput`][pythonnative.TextInput],
controlled patterns with [`use_state`][pythonnative.use_state], and
how to wire submission.

## The code

```python
import pythonnative as pn


def is_valid_email(s: str) -> bool:
    return "@" in s and "." in s.split("@", 1)[-1]


@pn.component
def LabeledInput(label, value, on_change, placeholder="", error=None, secure=False):
    return pn.Column(
        pn.Text(label, style={"font_size": 14, "bold": True}),
        pn.TextInput(
            value=value,
            on_change=on_change,
            placeholder=placeholder,
            secure_text_entry=secure,
        ),
        pn.Text(
            error or "",
            style={"font_size": 12, "color": "#ff3b30"},
        ),
        style={"spacing": 4},
    )


@pn.component
def SignUp():
    name, set_name = pn.use_state("")
    email, set_email = pn.use_state("")
    password, set_password = pn.use_state("")
    submitting, set_submitting = pn.use_state(False)
    submitted, set_submitted = pn.use_state(False)

    name_error = "Name is required" if not name.strip() else None
    email_error = "Enter a valid email" if email and not is_valid_email(email) else None
    password_error = "At least 8 characters" if password and len(password) < 8 else None

    has_errors = bool(name_error or email_error or password_error)
    can_submit = name and email and password and not has_errors and not submitting

    def submit():
        if not can_submit:
            return
        set_submitting(True)
        # Simulate work; in a real app, post to an API here.
        set_submitted(True)
        set_submitting(False)

    if submitted:
        return pn.Column(
            pn.Text("Welcome!", style={"font_size": 28, "bold": True}),
            pn.Text(f"Account created for {name}.", style={"font_size": 16}),
            style={"spacing": 8, "padding": 16},
        )

    return pn.ScrollView(
        pn.Column(
            pn.Text("Sign up", style={"font_size": 28, "bold": True}),
            LabeledInput(
                label="Name",
                value=name,
                on_change=set_name,
                placeholder="Ada Lovelace",
                error=name_error if name else None,
            ),
            LabeledInput(
                label="Email",
                value=email,
                on_change=set_email,
                placeholder="ada@example.com",
                error=email_error,
            ),
            LabeledInput(
                label="Password",
                value=password,
                on_change=set_password,
                placeholder="At least 8 characters",
                error=password_error,
                secure=True,
            ),
            pn.Button(
                "Submitting..." if submitting else "Create account",
                on_press=submit,
                disabled=not can_submit,
            ),
            style={"spacing": 12, "padding": 16, "align_items": "stretch"},
        )
    )
```

## What's going on

- Each input is **controlled**: its `value` comes from state, and its
  `on_change` writes back into state. There is no separate "form
  state" object; the component itself is the source of truth.
- Validation is computed each render. Showing an error message only
  *after* the user has typed (the `if name` guard) avoids the "every
  field is red on first paint" trap.
- `can_submit` derives from the inputs and the in-flight state. The
  button is disabled while `submitting` is true, and the label
  reflects what's happening.
- The success view is just a different render path; no navigation is
  needed for a one-screen form.

## Async submission

For a real submission flow, hand the work to `asyncio`:

```python
import asyncio


def submit():
    if not can_submit:
        return
    set_submitting(True)

    async def go():
        try:
            await api.create_account(name=name, email=email, password=password)
            set_submitted(True)
        except Exception as exc:
            set_form_error(str(exc))
        finally:
            set_submitting(False)

    asyncio.create_task(go())
```

Wrap state updates that touch the same screen in a single setter when
possible (e.g., a single `dispatch` from a reducer) so the page only
re-renders once per user-visible change.

## Validation libraries

The validation here is hand-rolled for clarity. For more elaborate
forms, any pure-Python validation library (`pydantic`, `cerberus`,
`marshmallow`) drops in: validate from the input dict on each render,
and surface the resulting errors next to the inputs.

## Next steps

- Render a dynamic list: [Lists](lists.md).
- Wire forms into navigation: [Navigation](navigation.md).
- Make the form theme-aware: [Styling guide](../guides/styling.md).
