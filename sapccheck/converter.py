def convert_sapc_response(data):
    """
    Chuyển SAPC JSON sang JSON tham chiếu.
    Hỗ trợ bóc tách đầy đủ từ LUPersonalList, pcGroupList (HOME, ODA_BIG_OCS...) và FamilyProperties.
    """
    result = {
        "msisdn": str(data.get("MSISDN")),
        "packages": []
    }

    existing_pkg_names = set()

    # 1. Bảng tra cứu hạn sử dụng từ ADPersonalList
    ad_map = {}
    for item in (data.get("ADPersonalList") or []):
        group_name = item.get("groupName")
        if group_name:
            ad_map[group_name] = item

    # 2. Bóc tách LUPersonalList (Gói cá nhân thông thường)
    lu_list = data.get("LUPersonalList") or []
    for item in lu_list:
        group_name = item.get("groupName")
        pkg_name = item.get("description") or group_name
        ad_info = ad_map.get(group_name, {})

        result["packages"].append({
            "group_name": group_name,
            "package_name": pkg_name,
            "register_date": item.get("subscriptionDate"),
            "expire_date": ad_info.get("expireDate")
        })
        if pkg_name:
            existing_pkg_names.add(pkg_name.lower())

    # 3. Bóc tách pcGroupList (Gói HOME, Gói cước OCS như ODA_BIG_OCS...)
    # Bỏ qua các rule QoS / dịch vụ phụ không phải gói cước data độc lập
    APP_RULES = {"volte_group", "youtube", "tiktok", "dip_meta", "mi_mytv"}

    pc_list = data.get("pcGroupList") or []
    for item in pc_list:
        gname = item.get("groupName") or ""
        gname_lower = gname.lower()
        if not gname or gname_lower in APP_RULES:
            continue

        is_home = "home" in gname_lower
        is_ocs = "ocs" in gname_lower or gname_lower.startswith("oda_")

        # Bao gồm: gói HOME, gói OCS (ODA_BIG_OCS / BIG_OCS), hoặc khi LUPersonalList trống
        should_include = is_home or is_ocs or (len(lu_list) == 0)

        if should_include and gname_lower not in existing_pkg_names:
            result["packages"].append({
                "group_name": gname,
                "package_name": gname,
                "register_date": item.get("groupStartDate"),
                "expire_date": item.get("groupEndDate")
            })
            existing_pkg_names.add(gname_lower)

    # 4. Bóc tách FamilyProperties (Nhóm gia đình / Home kết nối)
    fam_props = data.get("FamilyProperties") or {}
    fam_groups = fam_props.get("pcGroupF") or []
    for item in fam_groups:
        if isinstance(item, dict):
            fgname = item.get("groupName") or ""
        else:
            fgname = str(item)
        if fgname and fgname.lower() not in existing_pkg_names:
            result["packages"].append({
                "group_name": fgname,
                "package_name": fgname,
                "register_date": None,
                "expire_date": None
            })
            existing_pkg_names.add(fgname.lower())

    return result