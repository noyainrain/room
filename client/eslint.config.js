// @ts-nocheck

import js from "@eslint/js";

export default [
    js.configs.recommended,
    {
        linterOptions: {
            reportUnusedDisableDirectives: true
        },
        rules: {
            // Follow Crockford style (see https://crockford.com/code.html)
            "array-bracket-newline": ["error", "consistent"],
            "array-bracket-spacing": "error",
            "arrow-parens": ["error", "as-needed"],
            "arrow-spacing": "error",
            "block-spacing": "error",
            "brace-style": "error",
            "comma-dangle": "error",
            "comma-spacing": "error",
            "comma-style": "error",
            "computed-property-spacing": "error",
            "dot-location": "error",
            "eol-last": "error",
            "func-call-spacing": "error",
            "function-paren-newline": ["error", "consistent"],
            "generator-star-spacing": "error",
            "implicit-arrow-linebreak": "error",
            "indent": "error",
            "jsx-quotes": "off",
            "key-spacing": "error",
            "keyword-spacing": "error",
            "line-comment-position": "error",
            "linebreak-style": "error",
            "max-len": ["error", {code: 100, ignoreStrings: true}],
            "max-statements-per-line": "error",
            "new-parens": "error",
            "no-mixed-spaces-and-tabs": "error",
            "no-multi-spaces": "error",
            "no-multiple-empty-lines": "error",
            "no-tabs": "error",
            "no-trailing-spaces": "error",
            "no-whitespace-before-property": "error",
            "nonblock-statement-body-position": "error",
            "object-curly-newline": ["error", {consistent: true}],
            "object-curly-spacing": "error",
            "operator-linebreak": "error",
            "quotes": ["error", "double", {avoidEscape: true}],
            "rest-spread-spacing": "error",
            "semi": "error",
            "semi-spacing": "error",
            "semi-style": "error",
            "space-before-blocks": "error",
            "space-before-function-paren": ["error", {named: "never"}],
            "space-in-parens": "error",
            "space-infix-ops": "error",
            "space-unary-ops": "error",
            "switch-colon-spacing": "error",
            "template-curly-spacing": "error",
            "template-tag-spacing": "error",
            "unicode-bom": "error",
            "wrap-iife": "error",
            "wrap-regex": "error",
            "yield-star-spacing": "error",
            // Line breaks help structure the thought process
            "array-element-newline": "off",
            "function-call-argument-newline": "off",
            "lines-around-comment": "off",
            "lines-between-class-members": "off",
            "multiline-ternary": "off",
            "newline-per-chained-call": "error",
            "object-property-newline": "off",
            "padding-line-between-statements": "off",
            // Handled by TypeScript
            "no-undef": "off",
            "no-extra-parens": "off",
            // Additional best practices
            "no-warning-comments": "error"
        }
    }
];
