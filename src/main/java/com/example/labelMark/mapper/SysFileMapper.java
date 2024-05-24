package com.example.labelMark.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.labelMark.domain.SysFile;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;

/**
 * <p>
 * Mapper 接口
 * </p>
 *
 * @author hjw
 * @since 2024-04-18
 */
@Mapper
public interface SysFileMapper extends BaseMapper<SysFile> {

    @Select({
            "<script>",
            "SELECT * FROM file",
            "ORDER BY file_id DESC",
            "LIMIT #{pageSize} OFFSET #{offset}",
            "</script>"
    })
    List<SysFile> getAllFiles(Integer current, Integer pageSize, Integer fileId, int offset);

    @Update("update sysFile set file_name=#{fileName}, update_time=now() where file_id=#{fileId}")
    void updateFile(Integer fileId, String fileName);


    @Insert("INSERT INTO file(file_name, update_time, status, size) values (#{fileName}, #{updateTime}, 0, #{size})")
    void createFile(String fileName, String updateTime, String size);
}
