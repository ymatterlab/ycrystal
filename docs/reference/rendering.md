# POV export and render jobs

::: ycrystal.render.pov_writer
    options:
      members:
        - RenderSettings
        - scene_to_pov
        - render_ini
        - write_scene_files

::: ycrystal.render.povray
    options:
      members:
        - PovrayNotFoundError
        - find_povray
        - povray_version
        - explain_failure

::: ycrystal.render.jobs
    options:
      members:
        - RenderResult
        - prepare_job
        - finish_job
        - run_job
        - copy_result

::: ycrystal.render.jobs.RenderJob
    options:
      members:
        - arguments
        - cleanup

::: ycrystal.render.selftest
    options:
      members:
        - TOLERANCE_PX
        - SelfTestResult
        - run_self_test
