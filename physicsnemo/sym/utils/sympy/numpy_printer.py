# SPDX-FileCopyrightText: Copyright (c) 2023 - 2024 NVIDIA CORPORATION & AFFILIATES.
# SPDX-FileCopyrightText: All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Helper functions for converting sympy equations to numpy
"""

import types
import inspect
import numpy as np
import symengine as se
import sympy as sp
import sys

NP_LAMBDA_STORE = {}


def _get_function_argspec(func):
    if sys.version_info >= (3, 11):
        sig = inspect.signature(func)  # Use the latest function in 3.11+
        return {
            "args": [
                param
                for param in sig.parameters
                if sig.parameters[param].kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ],
            "varargs": next(
                (
                    param
                    for param in sig.parameters
                    if sig.parameters[param].kind == inspect.Parameter.VAR_POSITIONAL
                ),
                None,
            ),
            "varkw": next(
                (
                    param
                    for param in sig.parameters
                    if sig.parameters[param].kind == inspect.Parameter.VAR_KEYWORD
                ),
                None,
            ),
            "defaults": [
                param.default
                for param in sig.parameters.values()
                if param.default is not param.empty
            ],
            "kwonlyargs": [
                param
                for param in sig.parameters
                if sig.parameters[param].kind == inspect.Parameter.KEYWORD_ONLY
            ],
        }
    else:
        argspec = inspect.getfullargspec(func)  # Backward-compatible approach
        return {
            "args": argspec.args,
            "varargs": argspec.varargs,
            "varkw": argspec.varkw,
            "defaults": argspec.defaults,
            "kwonlyargs": argspec.kwonlyargs,
        }


def np_lambdify(f, r):
    """
    generates a numpy function from a sympy equation

    Parameters
    ----------
    f : Sympy Exp, float, int, bool or list of the previous
      the equation to convert to a numpy function.
      If float, int, or bool this gets converted
      to a constant function of value `f`. If f is a list
      then output for each element in list is is
      concatenated on axis -1.
    r : list, dict
      A list of the arguments for `f`. If dict then
      the keys of the dict are used.

    Returns
    -------
    np_f : numpy function
    """

    # possibly lambdify list of f
    if not isinstance(f, list):
        f = [f]

    # convert r to a list if dictionary
    # break up any tuples to elements in list
    if isinstance(r, dict):
        r = list(r.keys())
    no_tuple_r = []
    for key in r:
        if isinstance(key, tuple):
            for k in key:
                no_tuple_r.append(k)
        else:
            no_tuple_r.append(key)

    # lambidfy all functions in list
    lambdify_f = []
    for f_i in f:
        # check if already a numpy function
        if isinstance(f_i, types.FunctionType):
            # add r inputs to function
            args = _get_function_argspec(f_i)["args"]

            def lambdify_f_i(**x):
                return f_i(**{key: x[key] for key in args})

        else:
            # check if already lambdified equation
            if (f_i, tuple(no_tuple_r)) in NP_LAMBDA_STORE.keys():
                lambdify_f_i = NP_LAMBDA_STORE[(f_i, tuple(no_tuple_r))]
            else:  # if not lambdify it
                try:
                    if not isinstance(f_i, bool):
                        f_i = float(f_i)
                except:
                    pass
                if isinstance(f_i, (float, int)):  # constant function

                    def loop_lambda(constant):
                        return (
                            lambda **x: np.zeros_like(next(iter(x.items()))[1])
                            + constant
                        )

                    lambdify_f_i = loop_lambda(f_i)
                elif type(f_i) in [
                    type((se.Symbol("x") > 0).subs(se.Symbol("x"), 1)),
                    type((se.Symbol("x") > 0).subs(se.Symbol("x"), -1)),
                    bool,
                ]:  # TODO hacky sympy boolian check

                    def loop_lambda(constant):
                        if constant:
                            return lambda **x: np.ones_like(
                                next(iter(x.items()))[1], dtype=bool
                            )
                        else:
                            return lambda **x: np.zeros_like(
                                next(iter(x.items()))[1], dtype=bool
                            )

                    lambdify_f_i = loop_lambda(f_i)
                else:
                    try:  # first try to compile with Symengine
                        kk = []
                        for k in no_tuple_r:
                            if isinstance(k, str):
                                kk.append(se.Symbol(k))
                            else:
                                kk.append(k)
                        kk = [se.Symbol(name) for name in sorted([x.name for x in kk])]
                        se_lambdify_f_i = se.lambdify(kk, [f_i], backend="llvm")

                        def lambdify_f_i(**x):
                            if len(x) == 1:
                                v = list(x.values())[0]
                            else:
                                v = np.stack(
                                    [v for v in dict(sorted(x.items())).values()],
                                    axis=-1,
                                )
                            out = se_lambdify_f_i(v)
                            if isinstance(out, list):
                                out = np.concatenate(out, axis=-1)
                            return out

                    except:  # fall back on older SymPy compile
                        sp_lambdify_f_i = sp.lambdify(
                            [k for k in no_tuple_r], f_i, [NP_SYMPY_PRINTER, "numpy"]
                        )

                        def lambdify_f_i(**x):
                            v = sp_lambdify_f_i(**x)
                            if isinstance(v, list):
                                v = np.concatenate(v, axis=-1)
                            return v

            # add new lambdified function to dictionary
            NP_LAMBDA_STORE[(f_i, tuple(no_tuple_r))] = lambdify_f_i

        # add new list of lambda functions
        lambdify_f.append(lambdify_f_i)

    # construct master lambda function for all
    def loop_grouped_lambda(lambdify_f):
        def grouped_lambda(**invar):
            output = []
            for lambdify_f_i in lambdify_f:
                output.append(lambdify_f_i(**invar))
            return np.concatenate(output, axis=-1)

        return grouped_lambda

    return loop_grouped_lambda(lambdify_f)


def _xor_np(x):
    return np.logical_xor(x)


def _min_np(x, axis=None):
    return_value = x[0]
    for value in x:
        return_value = np.minimum(return_value, value)
    return return_value


def _max_np(x, axis=None):
    return_value = x[0]
    for value in x:
        return_value = np.maximum(return_value, value)
    return return_value


def _heaviside_np(x, x2=0):
    # force x2 to 0
    x2 = 0
    return np.heaviside(x, x2)


def _equal_np(x, y):
    return np.isclose(x, y)


NP_SYMPY_PRINTER = {
    "amin": _min_np,
    "amax": _max_np,
    "Heaviside": _heaviside_np,
    "equal": _equal_np,
    "Xor": _xor_np,
}

SYMENGINE_BLACKLIST = [sp.Heaviside, sp.DiracDelta]
