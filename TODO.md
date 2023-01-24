## Python3 bootstrap-compiler

- [X] support `import { self, File } from "std/fs"`.
- [X] fix `if let x = result_fn() { ... }`.
- [X] fix `+=` operators with overloaded operators.
- [X] implement `switch 1 { 2 if abc => { ... } }`.
- [X] implement `switch advance_enum_obj is { .Value as val => { ... } }`.
- [X] check advance enums casts.
- [X] `@vec` builtin function.
- [X] mutable arrays/vectors: `[]mut T`/`[SIZE]mut T`.
- [X] `for &v in iterable {` and `for mut v in iterable`.

## Self-hosted compiler

- [ ] add `HashMap<K, V>`.
- [ ] constant-folding.
- [ ] optimize code.
- [ ] function literals.
- [ ] anonymous structs.
- [ ] better support for embedded structs.
- [ ] reference counting for traits, advance enums, strings and vectors.
- [ ] do not modify the values of primitive types passed as an argument that is 
declared mutable (this should only work with reference types):
    ```ri
    func arg(mut x: i32) {
        x += 1;
    }

    y := 1;
    arg(y); // `y` should not be modified, and the compiler should not require 
            // it to be a mutable variable.
    ```
- [ ] `undefined` for uninitialized variables.
- [ ] disallow empty array literal (`let x = []!; -> ERROR`).
- [ ] check correct implementation of a trait.
- [ ] disallow use of references outside of functions.
- [ ] add `@is_flag_defined()` builtin function.
