return {
  s("$", {
    t '$("',
    i(1),
    t '")',
  }),
  s({ trig = "con", dsrc = "console.log()" }, {
    t "console.log(",
    i(1),
    t ")",
  }),
  s("debug", {
    t "console.log('debug')",
  }),
}
