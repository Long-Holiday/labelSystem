package com.example.labelMark.mapper;

import com.example.labelMark.domain.Mark;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.*;

/**
 * <p>
 *  Mapper 接口
 * </p>
 *
 * @author hjw
 * @since 2024-04-28
 */
@Mapper
public interface MarkMapper extends BaseMapper<Mark> {

    @Select("SELECT COUNT(*) FROM mark WHERE task_id=#{taskId}}")
    int isMark(int taskId);


    @Delete("DELETE FROM mark where mark_name=#{markName}")
    void deleteMarkByName(String markName);

    @Delete("DELETE FROM mark WHERE task_id=#{taskId} AND type_id=#{typeId}")
    void deleteMark(int taskId, int typeId);

    @Insert("INSERT INTO mark(task_id, type_id, geom) values (#{taskId},#{typeId},#{geom})")
    Mark createMark(int taskId, int typeId, String geom);

//    @Insert()
//    void createMark(String markName);
}
