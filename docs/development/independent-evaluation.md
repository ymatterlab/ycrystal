# Independent evaluation checklist

For Computer Programs articles, the *Journal of Applied Crystallography* expects the
program's usefulness and the adequacy of its documentation to be shown by **at least
two independent users**: users who are not colleagues or close collaborators of the
authors. The submission asks for brief reports from them, which are used in the review
and not published. The journal also expects a web page with documentation and
downloads, and anonymous access for referees. Sources: the
[notes for authors](https://journals.iucr.org/j/services/notesforauthors.html) and the
[submission instructions](https://journals.iucr.org/j/services/new_submitinstructions.html),
as summarised by a search on 17 November 2026; the pages themselves refused automated
access, so check the current wording before submitting.

This checklist is what the authors send to each evaluator. It is a set of tasks and
questions, not code.

The answers must be the evaluators' own: record them as received, and do not edit,
summarise, or complete them on an evaluator's behalf. Nothing in this repository is an
evaluation result until an evaluator has written it.

## For the authors, before sending

- [ ] Choose two evaluators who did not take part in developing Ycrystal and are not
      close collaborators of the authors, ideally on different systems (Linux, macOS).
- [ ] Give access to the repository at a **tagged version**, and write that version
      here: ________.
- [ ] Send this page and nothing else as instructions. Do not demonstrate the program
      beforehand; how the documentation alone works is part of the evaluation.
- [ ] Agree how the answers will be returned (a signed document or an e-mail) and that
      they will be given to the journal for the review with the evaluator's name.
- [ ] Referees need anonymous access to the program: the repository is private at the
      time of writing, so decide how to provide it before submitting.

## For the evaluator

Please work alone, with the documentation of the repository (`README.md` and `docs/`),
and note where you got stuck, even if you found a way around it. Expect about two to
three hours. Use your own structures where you can; the repository's
`tests/fixtures/` and `examples/` folders have some to start with.

**About you and your computer.**

- [ ] Your field and how you usually make crystal-structure figures (programs used):
      ________
- [ ] Operating system and version, processor: ________
- [ ] `ycrystal --version` and `ycrystal --check-renderer` output: ________

**Tasks.** For each task note the time it took, whether it worked, and any problem.

- [ ] **1. Install** Ycrystal and POV-Ray following the installation guide
      (`docs/guide/install.md`).
- [ ] **2. Make a figure in the window.** Open a structure file (CIF, POSCAR, or
      Quantum ESPRESSO input), choose the repetitions, materials, a background, and a
      view, then render a PNG (*Render ▸ Render Image…*). Follow
      `docs/guide/first-figure.md` if you like.
- [ ] **3. Reuse the look.** Save the look as a style (*File ▸ Export Style…*) and apply
      it to a second structure with *File ▸ Import Style…*. Then apply the supplied
      style `examples/publication/styles/paper.ycstyle` to a material of your own. If a
      structure has other elements than the style, try the element mapping in that
      dialog.
- [ ] **4. From the command line.** Apply the same style to a third structure with
      `ycrystal FILE --style STYLE.ycstyle --render OUT.png`, with a view such as
      `--view c` (`docs/guide/examples.md`).
- [ ] **5. A series.** Copy `examples/publication/gallery.json` (or
      `examples/batch-series.json`), change it to render three of your own structures
      with your style, and run it with `--batch … --output-dir …`.
- [ ] **6. Reproduce a figure.** Render one figure with `--save-project FIGURE.ycrystal`,
      move or delete its structure file and style, and render the snapshot again
      (`docs/guide/reproducibility.md`). Compare the two images. Then re-open the
      snapshot in the window (*File ▸ Open…*) and check that it looks as rendered.
- [ ] **7. Optional.** Send the snapshot to the other evaluator or a colleague and ask them
      to render it on their computer.

**Questions.** Please answer in your own words.

1. Which tasks worked without help from anyone? Where did the documentation not answer
   your question, or answer it wrongly?
2. Which messages (warnings, errors) were unclear?
3. Did the images look as you expected? Did anything look wrong (positions, colours,
   cut-off figures, lighting)?
4. For your own research, what would you use Ycrystal for, if anything? What is
   missing for you?
5. Compared with the programs you use now, what is easier, harder, or impossible?
6. Any bugs, crashes, or data that would not open (please attach the file if you may
   share it).
7. Would you recommend Ycrystal to a colleague, and for what?

**Signature.** Name, affiliation, date, and a statement that you have no close
collaboration with the authors: ________
